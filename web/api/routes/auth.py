# forge/web/api/routes/auth.py
"""
Authentication routes — Login, Register (with OTP), Forgot Password, Reset Password
Enterprise: portal-separated login, admin create-user

RBAC role values:
    individual        — regular hacker user
    enterprise_staff  — teacher / staff created by enterprise admin
    enterprise_admin  — enterprise administrator
"""
import uuid
import secrets
import random
import os
import bcrypt
from datetime import datetime, timedelta

import resend
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
from jose import jwt
from web.api.dependencies import db
from web.api.config import logger
from web.api.limiter import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ─── Config ───────────────────────────────────────────────────────────────────

resend.api_key = os.getenv("RESEND_API_KEY")

FRONTEND_URL                = os.getenv("FRONTEND_URL", "http://localhost:3000")
SKIP_EMAIL_VERIFICATION     = os.getenv("SKIP_EMAIL_VERIFICATION", "false").lower() in ("true", "1", "yes")
RESET_TOKEN_TTL_MINUTES     = 30
OTP_TTL_MINUTES             = 5
OTP_MAX_ATTEMPTS            = 3

JWT_SECRET    = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise ValueError("FATAL ERROR: JWT_SECRET environment variable is not set!")

JWT_ALGORITHM = "HS256"
JWT_TTL_DAYS  = 7

EMAIL_FROM_NAME    = os.getenv("EMAIL_FROM_NAME", "ctfWithAi")
EMAIL_FROM_ADDRESS = os.getenv("EMAIL_FROM_ADDRESS", "onboarding@resend.dev")
EMAIL_FROM         = f"{EMAIL_FROM_NAME} <{EMAIL_FROM_ADDRESS}>"

ENTERPRISE_ROLES = ("enterprise_staff", "enterprise_admin")

# ── Internal API key for Appsmith — add INTERNAL_API_KEY to your .env ─────────
# Generate: python -c "import secrets; print(secrets.token_hex(32))"
# Set the same value in Appsmith Headers as:  X-Internal-Key: <your_value>
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY")
if not INTERNAL_API_KEY:
    raise ValueError("FATAL ERROR: INTERNAL_API_KEY environment variable is not set!")


# ─── Password Helpers ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ─── JWT Helpers ──────────────────────────────────────────────────────────────

def create_token(
    user_id: str,
    username: str,
    role: str,
    organization_id: str | None = None,
) -> str:
    now = datetime.utcnow()
    payload = {
        "sub":             user_id,
        "username":        username,
        "role":            role,
        "organization_id": organization_id,
        "iat":             now,
        "jti":             uuid.uuid4().hex,
        "exp":             now + timedelta(days=JWT_TTL_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception as e:
        logger.warning(f"[SECURITY ALERT] JWT Validation Failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token.")


# ─── Auth Dependencies ────────────────────────────────────────────────────────

def get_current_user(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header.")
    token = auth_header[7:]
    return decode_token(token)


def require_roles(*allowed_roles: str):
    def _guard(request: Request) -> dict:
        payload = get_current_user(request)
        if payload.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Access denied.")
        return payload
    return _guard


# ─── Request / Response Models ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email:    str
    password: str
    portal:   str = "individual"

class RegisterRequest(BaseModel):
    username:  str
    full_name: str
    email:     str
    password:  str
    role:      str = "individual"

class VerifyOTPRequest(BaseModel):
    email: str
    otp:   str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token:        str
    new_password: str

class EnterpriseUserCreateRequest(BaseModel):
    first_name: str
    last_name:  str = ""
    email:      str
    password:   str

# ── NEW ───────────────────────────────────────────────────────────────────────
class EnterpriseAdminCreateRequest(BaseModel):
    organization_name: str
    email:             str
    password:          str

class EnterpriseStaffUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name:  Optional[str] = None
    email:      Optional[str] = None
    password:   Optional[str] = None


# ─── Email Helpers ────────────────────────────────────────────────────────────

def _send_otp_email(to_email: str, otp: str, username: str) -> None:
    html = f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#000;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#000;padding:40px 0;">
    <tr><td align="center">
      <table width="420" cellpadding="0" cellspacing="0"
             style="background:#0a0a0a;border:1px solid #1f1f1f;border-radius:16px;padding:36px 32px;">
        <tr>
          <td align="center" style="padding-bottom:24px;">
            <div style="width:52px;height:52px;border-radius:14px;background:rgba(255,115,0,0.12);
                        border:1px solid rgba(255,115,0,0.3);display:inline-block;text-align:center;
                        line-height:52px;font-size:24px;">🛡️</div>
            <h1 style="color:#fff;font-size:20px;font-weight:700;margin:12px 0 4px;">ctfWithAi</h1>
            <p style="color:#555;font-size:13px;margin:0;">Verify your email address</p>
          </td>
        </tr>
        <tr>
          <td style="color:#888;font-size:13px;line-height:1.7;padding-bottom:24px;">
            <p style="margin:0;">Hi <strong style="color:#fff;">{username}</strong>, thanks for signing up!
            Enter the code below to verify your email and activate your account.</p>
          </td>
        </tr>
        <tr>
          <td align="center" style="padding-bottom:24px;">
            <div style="display:inline-block;background:#111;border:2px solid #ff7300;
                        border-radius:12px;padding:18px 40px;">
              <span style="font-size:36px;font-weight:900;letter-spacing:12px;color:#ff7300;font-family:monospace;">
                {otp}
              </span>
            </div>
            <p style="color:#555;font-size:11px;margin:10px 0 0;">
              Expires in <strong style="color:#fff;">{OTP_TTL_MINUTES} minutes</strong>.
              You have <strong style="color:#fff;">{OTP_MAX_ATTEMPTS} attempts</strong>.
            </p>
          </td>
        </tr>
        <tr>
          <td style="border-top:1px solid #1a1a1a;padding-top:20px;">
            <p style="color:#444;font-size:11px;line-height:1.6;margin:0;text-align:center;">
              If you didn't create a ctfWithAi account, you can safely ignore this email.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>""".strip()

    try:
        resend.Emails.send({
            "from":    EMAIL_FROM,
            "to":      to_email,
            "subject": f"{otp} is your ctfWithAi verification code",
            "html":    html,
        })
    except Exception as e:
        logger.error(f"OTP email failed for {to_email}: {e}")
        raise RuntimeError("Failed to send verification email. Please try again.")


def _send_reset_email(to_email: str, reset_link: str) -> None:
    html = f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#000;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#000;padding:40px 0;">
    <tr><td align="center">
      <table width="420" cellpadding="0" cellspacing="0"
             style="background:#0a0a0a;border:1px solid #1f1f1f;border-radius:16px;padding:36px 32px;">
        <tr>
          <td align="center" style="padding-bottom:24px;">
            <div style="width:52px;height:52px;border-radius:14px;background:rgba(255,115,0,0.12);
                        border:1px solid rgba(255,115,0,0.3);display:inline-block;text-align:center;
                        line-height:52px;font-size:24px;">🛡️</div>
            <h1 style="color:#fff;font-size:20px;font-weight:700;margin:12px 0 4px;">ctfWithAi</h1>
            <p style="color:#555;font-size:13px;margin:0;">Password Reset Request</p>
          </td>
        </tr>
        <tr>
          <td style="color:#888;font-size:13px;line-height:1.7;padding-bottom:28px;">
            <p style="margin:0 0 12px;">We received a request to reset the password for
            <span style="color:#ff7300;">{to_email}</span>.</p>
            <p style="margin:0;">This link is valid for
            <strong style="color:#fff;">{RESET_TOKEN_TTL_MINUTES} minutes</strong>.</p>
          </td>
        </tr>
        <tr>
          <td align="center" style="padding-bottom:28px;">
            <a href="{reset_link}" style="display:inline-block;padding:12px 32px;background:#ff7300;
               color:#fff;font-size:14px;font-weight:700;border-radius:10px;text-decoration:none;">
              Reset Password
            </a>
          </td>
        </tr>
        <tr>
          <td style="padding-bottom:20px;">
            <p style="color:#444;font-size:11px;line-height:1.6;margin:0;text-align:center;">
              Button not working? Copy this link:<br>
              <span style="color:#ff7300;word-break:break-all;">{reset_link}</span>
            </p>
          </td>
        </tr>
        <tr>
          <td style="border-top:1px solid #1a1a1a;padding-top:20px;">
            <p style="color:#444;font-size:11px;line-height:1.6;margin:0;text-align:center;">
              If you didn't request this, you can safely ignore this email.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>""".strip()

    try:
        resend.Emails.send({
            "from":    EMAIL_FROM,
            "to":      to_email,
            "subject": "ctfWithAi — Password Reset Request",
            "html":    html,
        })
    except Exception as e:
        logger.error(f"Reset email failed for {to_email}: {e}")
        raise RuntimeError("Failed to send email. Please try again later.")


# ─── Login ────────────────────────────────────────────────────────────────────

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest):
    email = body.email.strip().lower()
    portal = body.portal.strip().lower()

    user = db.get_any_user_by_email(email)

    if not user or not verify_password(body.password, user.get("password", "")):
        logger.warning(f"[SECURITY ALERT] Failed login attempt for email: {email} from IP: {request.client.host}")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id         = user.get("user_id")
    username        = user.get("username", user.get("email", "User").split("@")[0])
    role            = user.get("role", "individual")
    organization_id = user.get("organization_id")

    if portal == "enterprise":
        if role not in ENTERPRISE_ROLES:
            raise HTTPException(status_code=403, detail="This account does not have enterprise access.")
    else:
        if role in ENTERPRISE_ROLES:
            raise HTTPException(status_code=403, detail="Please use the enterprise login page.")

    token = create_token(user_id, username, role, organization_id)
    logger.info(f"User logged in: {user_id} (role={role})")

    if role == "enterprise_admin":
        redirect_url = "/enterprise/admin/dashboard"
    elif role == "enterprise_staff":
        redirect_url = "/enterprise/portal"
    else:
        redirect_url = "/dashboard"

    return {
        "token":        token,
        "userId":       user_id,
        "username":     username,
        "role":         role,
        "redirect_url": redirect_url,
        "message":      "Login successful"
    }


# ─── Register — Step 1 ───────────────────────────────────────────────────────

@router.post("/register")
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest):
    email    = body.email.strip().lower()
    username = body.username.strip()

    if db.get_any_user_by_email(email):
        raise HTTPException(status_code=400, detail="Email already in use")
    if db.get_user_by_username(username):
        raise HTTPException(status_code=400, detail="Username already taken")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    hashed_password = hash_password(body.password)

    if SKIP_EMAIL_VERIFICATION:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        role    = "individual"

        user_data = {
            "user_id":             user_id,
            "username":            username,
            "full_name":           body.full_name.strip(),
            "email":               email,
            "password":            hashed_password,
            "role":                role,
            "total_points":        0,
            "machines_solved":     0,
            "campaigns_completed": 0,
        }

        try:
            db.create_user(user_data)
            logger.info(f"New user created (email verification skipped): {user_id} ({email})")
        except Exception as e:
            logger.error(f"Failed to create user {user_id}: {e}")
            raise HTTPException(status_code=400, detail="Registration failed. Please try again.")

        token = create_token(user_id, username, role)
        return {
            "token":    token,
            "userId":   user_id,
            "username": username,
            "role":     role,
            "message":  "Account created successfully!",
            "verified": True,
        }

    otp        = str(secrets.randbelow(9000) + 1000)
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)

    db.create_pending_registration({
        "username":   username,
        "full_name":  body.full_name.strip(),
        "email":      email,
        "password":   hashed_password,
        "role":       "individual",
        "otp":        otp,
        "expires_at": expires_at,
    })

    try:
        _send_otp_email(email, otp, username)
        logger.info(f"OTP sent to: {email}")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "message": "OTP sent to your email. Please verify to complete registration.",
        "email":   email,
    }


# ─── Register — Step 2 ───────────────────────────────────────────────────────

@router.post("/register/verify")
@limiter.limit("5/minute")
async def verify_otp(request: Request, body: VerifyOTPRequest):
    email = body.email.strip().lower()
    otp   = body.otp.strip()

    pending = db.get_pending_registration(email)

    if not pending:
        raise HTTPException(status_code=400, detail="No pending registration found. Please sign up again.")

    if datetime.utcnow() > pending["expires_at"]:
        db.delete_pending_registration(email)
        raise HTTPException(status_code=400, detail="OTP has expired. Please sign up again to get a new code.")

    if pending["attempts"] >= OTP_MAX_ATTEMPTS:
        db.delete_pending_registration(email)
        raise HTTPException(status_code=400, detail="Too many wrong attempts. Please sign up again.")

    if not secrets.compare_digest(otp, pending["otp"]):
        new_attempts = db.increment_otp_attempts(email)
        remaining    = OTP_MAX_ATTEMPTS - new_attempts
        if remaining <= 0:
            db.delete_pending_registration(email)
            raise HTTPException(status_code=400, detail="Too many wrong attempts. Please sign up again.")
        raise HTTPException(status_code=400,
            detail=f"Incorrect OTP. {remaining} attempt{'s' if remaining != 1 else ''} remaining.")

    user_id  = f"user_{uuid.uuid4().hex[:12]}"
    username = pending["username"]
    role     = "individual"

    user_data = {
        "user_id":             user_id,
        "username":            username,
        "full_name":           pending.get("full_name", ""),
        "email":               pending["email"],
        "password":            pending["password"],
        "role":                role,
        "total_points":        0,
        "machines_solved":     0,
        "campaigns_completed": 0,
    }

    try:
        db.create_user(user_data)
        logger.info(f"New verified user created: {user_id} ({email})")
    except Exception as e:
        logger.error(f"Failed to create user {user_id}: {e}")
        raise HTTPException(status_code=400, detail="Registration failed. Please try again.")

    db.delete_pending_registration(email)
    token = create_token(user_id, username, role)

    return {
        "token":    token,
        "userId":   user_id,
        "username": username,
        "role":     role,
        "message":  "Account verified and created successfully!"
    }


# ─── Forgot Password ──────────────────────────────────────────────────────────

@router.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest):
    email = body.email.strip().lower()
    user  = db.get_any_user_by_email(email)

    if user and user.get("role", "individual") in ENTERPRISE_ROLES:
        raise HTTPException(status_code=403,
            detail="Password reset is not available for enterprise accounts. Contact your administrator.")

    if user:
        token      = secrets.token_urlsafe(48)
        expires_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
        db.save_reset_token(token, email, expires_at)
        reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
        try:
            _send_reset_email(email, reset_link)
            logger.info(f"Password reset email sent to: {email}")
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        logger.info(f"Password reset for unregistered email: {email}")

    return {"message": "If that email is registered, a reset link has been sent."}


# ─── Reset Password ───────────────────────────────────────────────────────────

@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    token = body.token.strip()

    if not token:
        raise HTTPException(status_code=400, detail="Reset token is required.")
    if not body.new_password or len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    record = db.get_reset_token(token)

    if not record:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has already been used.")

    if datetime.utcnow() > record["expires_at"]:
        db.delete_reset_token(token)
        raise HTTPException(status_code=400, detail="This reset link has expired. Please request a new one.")

    email = record["email"]
    user  = db.get_any_user_by_email(email)

    if not user:
        db.delete_reset_token(token)
        raise HTTPException(status_code=404, detail="Account not found.")

    if user.get("role", "individual") in ENTERPRISE_ROLES:
        db.delete_reset_token(token)
        raise HTTPException(status_code=403,
            detail="Password reset is not available for enterprise accounts. Contact your administrator.")

    user_id = user.get("user_id")

    try:
        db.update_user(user_id, {"password": hash_password(body.new_password)})
        logger.info(f"Password reset for user: {user_id}")
    except Exception as e:
        logger.error(f"Failed to update password for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update password. Please try again.")

    db.delete_reset_token(token)
    return {"message": "Password updated successfully. You can now sign in."}


# ─── Enterprise: Admin creates staff/teacher account ─────────────────────────

@router.post("/enterprise/create-user")
async def enterprise_create_user(
    body: EnterpriseUserCreateRequest,
    caller: dict = Depends(require_roles("enterprise_admin")),
):
    email    = body.email.strip().lower()
    username = email.split("@")[0]

    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if db.get_any_user_by_email(email):
        raise HTTPException(status_code=400, detail="Email already in use.")
    if db.get_user_by_username(username):
        username = f"{username}_{uuid.uuid4().hex[:4]}"

    full_name = ""

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    hashed  = hash_password(body.password)
    org_id  = caller.get("organization_id")

    # Resolve org_name
    org = db.get_organization(org_id) if org_id else None
    org_name = org['name'] if org else ''

    staff_data = {
        "user_id":         user_id,
        "full_name":       full_name,
        "email":           email,
        "password":        hashed,
        "org_name":        org_name,
        "organization_id": org_id,
    }

    try:
        db.create_org_staff(staff_data)
        logger.info(f"Enterprise staff created: {user_id} by admin {caller.get('sub')}")
    except Exception as e:
        logger.error(f"Failed to create enterprise user: {e}")
        raise HTTPException(status_code=400, detail="Failed to create account. Please try again.")

    return {
        "userId":   user_id,
        "username": username,
        "email":    email,
        "role":     "enterprise_staff",
        "message":  "Staff account created successfully."
    }


# ─── NEW: Internal endpoint — ctfWithAi team creates enterprise org + admin ───
# Called ONLY via Appsmith by you. Protected by X-Internal-Key header.
# Add INTERNAL_API_KEY=<your_secret> to your .env file.
# Set the same value in Appsmith Headers: X-Internal-Key → <your_secret>

@router.post("/enterprise/create-admin")
async def create_enterprise_admin(request: Request, body: EnterpriseAdminCreateRequest):
    """
    Creates a new organization + enterprise_admin account in one call.
    Protected by a secret API key (X-Internal-Key header), NOT a JWT.
    This is the Tier 1 endpoint — bootstraps a new enterprise client.
    """

    # ── Verify internal API key ───────────────────────────────────────────────
    provided_key = request.headers.get("X-Internal-Key", "")
    if not provided_key or not secrets.compare_digest(provided_key, INTERNAL_API_KEY):
        logger.warning(f"[SECURITY ALERT] Unauthorized attempt to access Tier 1 Enterprise internal API from IP: {request.client.host}")
        raise HTTPException(status_code=403, detail="Access denied.")

    # ── Validate inputs ───────────────────────────────────────────────────────
    if not body.organization_name.strip():
        raise HTTPException(status_code=400, detail="Organization name is required.")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    email = body.email.strip().lower()

    if db.get_any_user_by_email(email):
        raise HTTPException(status_code=400, detail="Email already in use.")

    username = email.split("@")[0]
    if db.get_user_by_username(username):
        username = f"{username}_{uuid.uuid4().hex[:4]}"

    full_name = ""

    # ── Step 1: Create the organization ──────────────────────────────────────
    org_id = f"org_{uuid.uuid4().hex[:12]}"
    try:
        db.create_organization({
            "organization_id": org_id,
            "name":            body.organization_name.strip(),
        })
        logger.info(f"Organization created: {org_id} ({body.organization_name.strip()})")
    except Exception as e:
        logger.error(f"Failed to create organization: {e}")
        raise HTTPException(status_code=400, detail="Failed to create organization. Please try again.")

    # ── Step 2: Create the enterprise_admin in org_admins table ───────────
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    hashed  = hash_password(body.password)

    admin_data = {
        "user_id":         user_id,
        "email":           email,
        "password":        hashed,
        "org_name":        body.organization_name.strip(),
        "organization_id": org_id,
    }

    try:
        db.create_org_admin(admin_data)
        logger.info(f"Enterprise admin created: {user_id} for org {org_id}")
    except Exception as e:
        logger.error(f"Failed to create enterprise admin: {e}")
        raise HTTPException(status_code=400, detail="Failed to create admin account. Please try again.")

    return {
        "organizationId":   org_id,
        "organizationName": body.organization_name.strip(),
        "userId":           user_id,
        "username":         username,
        "email":            email,
        "role":             "enterprise_admin",
        "message":          "Enterprise organization and admin account created successfully."
    }


# ─── Enterprise: Admin lists staff accounts ───────────────────────────────────

@router.get("/enterprise/staff")
async def list_enterprise_staff(
    caller: dict = Depends(require_roles("enterprise_admin")),
):
    """
    Returns all staff accounts created under the admin's organization.
    """
    org_id = caller.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization linked to this admin account.")

    staff = db.get_staff_by_organization(org_id)
    return {"staff": staff, "count": len(staff)}


# ─── Enterprise: Admin updates a staff account ────────────────────────────────

@router.put("/enterprise/staff/{user_id}")
async def update_enterprise_staff(
    user_id: str,
    body: EnterpriseStaffUpdateRequest,
    caller: dict = Depends(require_roles("enterprise_admin")),
):
    """
    Allows the admin to update a staff account's name, email, or password.
    Validates that the target user belongs to the same organization.
    """
    org_id = caller.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="No organization linked to this admin account.")

    # Verify the target user exists and belongs to the same org
    target = db.get_org_staff(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Staff account not found.")
    if target.get("organization_id") != org_id:
        raise HTTPException(status_code=403, detail="This user does not belong to your organization.")
    if target.get("role") != "enterprise_staff":
        raise HTTPException(status_code=403, detail="You can only edit staff accounts.")

    update_fields = {}

    if body.first_name is not None or body.last_name is not None:
        first = body.first_name.strip() if body.first_name else ""
        last  = body.last_name.strip() if body.last_name else ""
        update_fields["full_name"] = f"{first} {last}".strip()

    if body.email is not None:
        new_email = body.email.strip().lower()
        if new_email != target.get("email"):
            existing = db.get_any_user_by_email(new_email)
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use.")
            update_fields["email"] = new_email

    if body.password is not None:
        if len(body.password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
        update_fields["password"] = hash_password(body.password)

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update.")

    try:
        db.update_org_staff(user_id, update_fields)
        logger.info(f"Staff {user_id} updated by admin {caller.get('sub')}: {list(update_fields.keys())}")
    except Exception as e:
        logger.error(f"Failed to update staff {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update account. Please try again.")

    return {"message": "Staff account updated successfully.", "updated_fields": list(update_fields.keys())}


# ══════════════════════════════════════════════════════════════════════════════
#  STUDENT LOGIN — authenticate students using account_id + password
# ══════════════════════════════════════════════════════════════════════════════

class StudentLoginRequest(BaseModel):
    account_id: str
    password:   str

@router.post("/student-login")
async def student_login(body: StudentLoginRequest, request: Request):
    """
    Authenticate a student using their account_id (roll number) and password
    (reversed roll number). Returns a JWT with student role details.
    """
    account_id = body.account_id.strip()
    password   = body.password.strip()

    if not account_id or not password:
        raise HTTPException(status_code=400, detail="Account ID and password are required.")

    # Look up in student_machine_instances
    student = db.get_student_by_account_id(account_id)
    if not student:
        raise HTTPException(status_code=401, detail="Invalid account ID or password.")

    # Verify bcrypt password
    if not bcrypt.checkpw(password.encode("utf-8"), student["hashed_password"].encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid account ID or password.")

    # Create JWT for student
    token = create_token(
        user_id=f"student_{student['instance_id']}",
        username=student["student_name"],
        role="student",
        organization_id=student.get("organization_id"),
    )

    logger.info(f"Student login: {account_id} (instance={student['instance_id']})")

    return {
        "token":         token,
        "userId":        f"student_{student['instance_id']}",
        "username":      student["student_name"],
        "role":          "student",
        "instance_id":   student["instance_id"],
        "assignment_id": student["assignment_id"],
        "machine_id":    student["machine_id"],
        "redirect_url":  "/student/dashboard",
    }