// src/components/AddStudents.jsx
// ─── Add Students Page — Enterprise Staff only ──────────────────────────────
// Provides manual student entry table + Excel import with auto-column-detection.

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
    ArrowLeft, Save, Upload, Plus, X, AlertCircle,
    CheckCircle, Loader, GraduationCap, FileSpreadsheet,
    AlertTriangle, Shield
} from 'lucide-react';
import * as XLSX from 'xlsx';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

// ─── Column auto-detection keywords ─────────────────────────────────────────
const COLUMN_KEYWORDS = {
    roll_no: ['roll', 'reg', 'registration', 'id', 'student id', 'reg#', 'roll no',
        'roll number', 'regno', 'enroll', 'enrollment', 'roll_no', 'rollno',
        'registration no', 'registration number'],
    student_name: ['name', 'student name', 'full name', 'student', 'sname',
        'student_name', 'studentname', 'fullname'],
    father_name: ['father', 'dad', 'father name', 'guardian', 'fname', 'f_name',
        'father_name', 'fathername', 'guardian name'],
    section: ['section', 'class', 'group', 'batch', 'sec'],
};

// Fields that must be mapped for import to succeed
const MANDATORY_FIELDS = ['roll_no', 'student_name'];

// ─── Create an empty student row ─────────────────────────────────────────────
const emptyRow = () => ({ roll_no: '', student_name: '', father_name: '', section: '', _key: Date.now() + Math.random() });


const AddStudents = () => {
    const role = localStorage.getItem('role') || '';

    // Guard: only enterprise_staff can see this
    if (role !== 'enterprise_staff') {
        return (
            <div className="min-h-[60vh] flex items-center justify-center">
                <div className="text-center space-y-4">
                    <div className="w-16 h-16 rounded-2xl bg-red-500/15 border border-red-500/30 flex items-center justify-center mx-auto">
                        <Shield className="w-8 h-8 text-red-500" />
                    </div>
                    <h2 className="text-2xl font-bold text-white">Access Denied</h2>
                    <p className="text-gray-500 text-sm max-w-md">
                        You don't have permission to access this page.
                    </p>
                </div>
            </div>
        );
    }

    return <AddStudentsContent />;
};


// ─── Main content (separated to avoid hooks-after-return) ────────────────────
const AddStudentsContent = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const editClassName = searchParams.get('edit'); // null if creating new
    const fileInputRef = useRef(null);

    // ── State ────────────────────────────────────────────────────────────────
    const [className, setClassName] = useState('');
    const [students, setStudents] = useState([emptyRow(), emptyRow(), emptyRow()]);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);
    const [validationErrors, setValidationErrors] = useState({}); // { rowIndex: ['roll_no', 'student_name'] }
    const [duplicateRolls, setDuplicateRolls] = useState(new Set());

    // Import state
    const [importStep, setImportStep] = useState(null); // null | 'mapping' | 'preview' | 'result'
    const [excelHeaders, setExcelHeaders] = useState([]);
    const [excelRows, setExcelRows] = useState([]);
    const [columnMapping, setColumnMapping] = useState({});
    const [previewRows, setPreviewRows] = useState([]);
    const [importResult, setImportResult] = useState(null);

    // ── Load existing class data if editing ──────────────────────────────────
    useEffect(() => {
        if (!editClassName) return;
        const loadClass = async () => {
            try {
                const token = localStorage.getItem('token');
                // First get all classes to verify it exists
                const classRes = await fetch(`${API_BASE}/api/enterprise/students/classes`, {
                    headers: { 'Authorization': `Bearer ${token}` },
                });
                if (!classRes.ok) throw new Error('Failed to load classes.');
                const classData = await classRes.json();
                const cls = (classData.classes || []).find(c => c.class_name === editClassName);
                if (!cls) {
                    setError('Class not found.');
                    return;
                }

                // We don't have a dedicated "get students for class" endpoint in the API,
                // but we can reconstruct from the class data. Let's use the update endpoint pattern.
                // Actually, we need to fetch students. Let me use the class name to query.
                // The API doesn't expose a GET for single class students, so let's create
                // a workaround: we'll send a GET request and parse from the students route.
                // Since our API only has GET /classes (list), we need to load students differently.
                // Let me add the class name to the request. Actually, let's just fetch all classes
                // and the students will need to come from the update flow.

                // We'll load students by trying to fetch them. For now, let's use the class name.
                setClassName(editClassName);

                // Fetch students for this class - we use the same GET /classes endpoint
                // but we need individual students. Let me use PUT's requirement to pre-check.
                // Actually, looking at our backend, get_class_students is used internally.
                // We should add a GET endpoint. But wait - let me check if our PUT endpoint returns students.
                // For the edit flow, we can add a query param to GET /classes.

                // Simpler: Let me fetch via a dedicated call. We'll need to add a small
                // endpoint or pass class_name as a query param. Let me add this to the GET.
                // Actually, let me just fetch - the backend get_class_students exists, 
                // I just didn't expose it. Let me use a query param approach on the GET endpoint.

                // For now, let's try fetching with a query parameter
                const studentsRes = await fetch(
                    `${API_BASE}/api/enterprise/students/classes?class_name=${encodeURIComponent(editClassName)}`,
                    { headers: { 'Authorization': `Bearer ${token}` } }
                );
                if (studentsRes.ok) {
                    const studentsData = await studentsRes.json();
                    if (studentsData.students && studentsData.students.length > 0) {
                        setStudents(studentsData.students.map(s => ({
                            roll_no: s.roll_no || '',
                            student_name: s.student_name || '',
                            father_name: s.father_name || '',
                            section: s.section || '',
                            _key: Date.now() + Math.random(),
                        })));
                    }
                }
            } catch (err) {
                setError(err.message);
            }
        };
        loadClass();
    }, [editClassName]);

    // ── Add a new empty row ──────────────────────────────────────────────────
    const addRow = () => {
        setStudents(prev => [...prev, emptyRow()]);
    };

    // ── Remove a row ─────────────────────────────────────────────────────────
    const removeRow = (index) => {
        setStudents(prev => prev.filter((_, i) => i !== index));
        // Clear validation errors for this row
        setValidationErrors(prev => {
            const next = { ...prev };
            delete next[index];
            return next;
        });
    };

    // ── Update a cell ────────────────────────────────────────────────────────
    const updateCell = (index, field, value) => {
        setStudents(prev => {
            const next = [...prev];
            next[index] = { ...next[index], [field]: value };
            return next;
        });
        // Clear validation for this cell
        setValidationErrors(prev => {
            const next = { ...prev };
            if (next[index]) {
                next[index] = next[index].filter(f => f !== field);
                if (next[index].length === 0) delete next[index];
            }
            return next;
        });
    };

    // ── Validate before save ─────────────────────────────────────────────────
    const validate = () => {
        const errors = {};
        const rollNos = [];
        const dupes = new Set();

        if (!className.trim()) {
            setError('Class name is required.');
            return false;
        }

        // Filter out completely empty rows
        const nonEmptyStudents = students.filter(
            s => s.roll_no.trim() || s.student_name.trim() || s.father_name.trim() || s.section.trim()
        );

        if (nonEmptyStudents.length === 0) {
            setError('At least one student is required.');
            return false;
        }

        students.forEach((s, i) => {
            // Skip completely empty rows
            if (!s.roll_no.trim() && !s.student_name.trim() && !s.father_name.trim() && !s.section.trim()) return;

            const rowErrors = [];
            if (!s.roll_no.trim()) rowErrors.push('roll_no');
            if (!s.student_name.trim()) rowErrors.push('student_name');
            if (rowErrors.length > 0) errors[i] = rowErrors;

            // Check duplicates
            if (s.roll_no.trim()) {
                if (rollNos.includes(s.roll_no.trim().toLowerCase())) {
                    dupes.add(s.roll_no.trim().toLowerCase());
                }
                rollNos.push(s.roll_no.trim().toLowerCase());
            }
        });

        setValidationErrors(errors);
        setDuplicateRolls(dupes);

        if (Object.keys(errors).length > 0) {
            setError('Please fix the highlighted errors before saving.');
            return false;
        }

        if (dupes.size > 0) {
            setError(`Duplicate Roll Numbers found: ${[...dupes].join(', ')}. Please fix before saving.`);
            return false;
        }

        return true;
    };

    // ── Save ─────────────────────────────────────────────────────────────────
    const handleSave = async () => {
        setError(null);
        setSuccess(null);
        if (!validate()) return;

        // Filter to only non-empty rows
        const validStudents = students
            .filter(s => s.roll_no.trim() && s.student_name.trim())
            .map(s => ({
                roll_no: s.roll_no.trim(),
                student_name: s.student_name.trim(),
                father_name: s.father_name.trim() || null,
                section: s.section.trim() || null,
            }));

        setSaving(true);
        try {
            const token = localStorage.getItem('token');
            const isEdit = !!editClassName;
            const url = isEdit
                ? `${API_BASE}/api/enterprise/students/class/${encodeURIComponent(editClassName)}`
                : `${API_BASE}/api/enterprise/students/class`;

            const res = await fetch(url, {
                method: isEdit ? 'PUT' : 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`,
                },
                body: JSON.stringify({
                    class_name: className.trim(),
                    students: validStudents,
                }),
            });

            if (!res.ok) {
                const body = await res.json().catch(() => ({}));
                throw new Error(body.detail || 'Failed to save class.');
            }

            setSuccess(`Class "${className.trim()}" saved with ${validStudents.length} students.`);
            setTimeout(() => navigate('/enterprise/portal'), 1200);
        } catch (err) {
            setError(err.message);
        } finally {
            setSaving(false);
        }
    };

    // ── Excel Import: Step 1 — Parse file ────────────────────────────────────
    const handleFileSelect = (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setError(null);

        const reader = new FileReader();
        reader.onload = (evt) => {
            try {
                const data = new Uint8Array(evt.target.result);
                const workbook = XLSX.read(data, { type: 'array' });
                const sheetName = workbook.SheetNames[0];
                const sheet = workbook.Sheets[sheetName];
                const jsonData = XLSX.utils.sheet_to_json(sheet, { defval: '' });

                if (jsonData.length === 0) {
                    setError('The selected file is empty or contains no data.');
                    return;
                }

                const headers = Object.keys(jsonData[0]);
                setExcelHeaders(headers);
                setExcelRows(jsonData);

                // Step 2: Auto-detect columns
                const mapping = autoDetectColumns(headers);
                setColumnMapping(mapping);

                // Check if mandatory fields are mapped
                const unmappedMandatory = MANDATORY_FIELDS.filter(f => !mapping[f]);
                if (unmappedMandatory.length > 0) {
                    // Show mapping UI for user to manually map
                    setImportStep('mapping');
                } else {
                    // All mandatory fields mapped — go straight to preview
                    generatePreview(mapping, jsonData);
                }
            } catch (err) {
                setError('Failed to parse the file. Please ensure it is a valid .xlsx or .xls file.');
            }
        };
        reader.readAsArrayBuffer(file);

        // Reset the input so the same file can be re-selected
        e.target.value = '';
    };

    // ── Auto-detect column mapping using keyword matching ────────────────────
    const autoDetectColumns = (headers) => {
        const mapping = {};
        const usedHeaders = new Set();

        for (const [field, keywords] of Object.entries(COLUMN_KEYWORDS)) {
            let bestMatch = null;
            let bestScore = 0;

            for (const header of headers) {
                if (usedHeaders.has(header)) continue;
                const headerLower = header.toLowerCase().trim();

                for (const keyword of keywords) {
                    // Exact match gets highest score
                    if (headerLower === keyword) {
                        if (3 > bestScore) {
                            bestScore = 3;
                            bestMatch = header;
                        }
                    }
                    // Header contains keyword
                    else if (headerLower.includes(keyword)) {
                        if (2 > bestScore) {
                            bestScore = 2;
                            bestMatch = header;
                        }
                    }
                    // Keyword contains header (partial match)
                    else if (keyword.includes(headerLower) && headerLower.length >= 3) {
                        if (1 > bestScore) {
                            bestScore = 1;
                            bestMatch = header;
                        }
                    }
                }
            }

            if (bestMatch && bestScore >= 1) {
                mapping[field] = bestMatch;
                usedHeaders.add(bestMatch);
            }
        }

        return mapping;
    };

    // ── Generate preview from mapping ────────────────────────────────────────
    const generatePreview = useCallback((mapping, rows) => {
        const preview = rows.map((row, idx) => {
            const mapped = {
                _originalRow: idx + 2, // +2 because row 1 is header, 0-indexed
                roll_no: String(row[mapping.roll_no] || '').trim(),
                student_name: String(row[mapping.student_name] || '').trim(),
                father_name: mapping.father_name ? String(row[mapping.father_name] || '').trim() : '',
                section: mapping.section ? String(row[mapping.section] || '').trim() : '',
                _valid: true,
                _reason: '',
            };

            if (!mapped.roll_no) {
                mapped._valid = false;
                mapped._reason = 'Missing Roll Number';
            } else if (!mapped.student_name) {
                mapped._valid = false;
                mapped._reason = 'Missing Student Name';
            }

            return mapped;
        });

        setPreviewRows(preview);
        setImportStep('preview');
    }, []);

    // ── Confirm Import ───────────────────────────────────────────────────────
    const confirmImport = () => {
        const valid = previewRows.filter(r => r._valid);
        const invalid = previewRows.filter(r => !r._valid);

        // Add valid rows to the student table
        const newRows = valid.map(r => ({
            roll_no: r.roll_no,
            student_name: r.student_name,
            father_name: r.father_name,
            section: r.section,
            _key: Date.now() + Math.random(),
        }));

        // Append to existing students (remove empty trailing rows first)
        setStudents(prev => {
            const nonEmpty = prev.filter(s => s.roll_no.trim() || s.student_name.trim());
            return [...nonEmpty, ...newRows];
        });

        setImportResult({
            imported: valid.length,
            skipped: invalid.length,
            skippedDetails: invalid.map(r => ({
                row: r._originalRow,
                reason: r._reason,
            })),
        });
        setImportStep('result');
    };

    // ── Handle mapping confirmation ──────────────────────────────────────────
    const confirmMapping = () => {
        const unmapped = MANDATORY_FIELDS.filter(f => !columnMapping[f]);
        if (unmapped.length > 0) {
            setError(`Please map the required fields: ${unmapped.map(f => f === 'roll_no' ? 'Roll No' : 'Student Name').join(', ')}`);
            return;
        }
        setError(null);
        generatePreview(columnMapping, excelRows);
    };

    // ── Check if a cell has a validation error ───────────────────────────────
    const hasError = (rowIndex, field) => {
        return validationErrors[rowIndex]?.includes(field);
    };

    const isDuplicate = (roll_no) => {
        return duplicateRolls.has(roll_no.trim().toLowerCase());
    };

    // ── Field label helper ───────────────────────────────────────────────────
    const fieldLabel = (field) => {
        switch (field) {
            case 'roll_no': return 'Roll No';
            case 'student_name': return 'Student Name';
            case 'father_name': return 'Father Name';
            case 'section': return 'Section';
            default: return field;
        }
    };


    // =========================================================================
    // RENDER
    // =========================================================================
    return (
        <div className="max-w-5xl mx-auto px-6 py-8">
            <style>{`
                @keyframes fadeUp {
                    from { opacity: 0; transform: translateY(16px); }
                    to   { opacity: 1; transform: translateY(0); }
                }
                .fade-in   { animation: fadeUp 0.4s ease both; }
                .fade-in-d { animation: fadeUp 0.4s ease 0.1s both; }
            `}</style>

            {/* Header */}
            <div className="flex items-center gap-4 mb-8 fade-in">
                <button
                    onClick={() => navigate('/enterprise/portal')}
                    className="w-10 h-10 rounded-lg bg-gray-900 border border-gray-800 flex items-center justify-center text-gray-400 hover:text-white hover:border-gray-700 transition-all"
                >
                    <ArrowLeft className="w-5 h-5" />
                </button>
                <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-2xl bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
                        <GraduationCap className="w-6 h-6 text-blue-400" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-white">
                            {editClassName ? 'Edit Class' : 'Add Students'}
                        </h1>
                        <p className="text-gray-500 text-sm">
                            {editClassName ? `Editing "${editClassName}"` : 'Create a new class and add students'}
                        </p>
                    </div>
                </div>
            </div>

            {/* Success */}
            {success && (
                <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-green-500/10 border border-green-500/25 mb-4 fade-in">
                    <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0" />
                    <p className="text-green-400 text-xs">{success}</p>
                </div>
            )}

            {/* Error */}
            {error && (
                <div className="flex items-center gap-2.5 px-3.5 py-2.5 rounded-lg bg-red-500/10 border border-red-500/25 mb-4 fade-in">
                    <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
                    <p className="text-red-400 text-xs">{error}</p>
                </div>
            )}

            {/* ── Section 1: Class Name ──────────────────────────────────────── */}
            <div className="rounded-xl border border-gray-900 bg-gray-950/60 p-5 mb-6 fade-in-d">
                <label className="block text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wider">
                    Class Name *
                </label>
                <input
                    type="text"
                    placeholder="e.g., BS-CS Section A, Cybersecurity Batch 2021"
                    value={className}
                    onChange={e => { setClassName(e.target.value); setError(null); }}
                    className={`w-full px-4 py-2.5 bg-[#0a0a0a] border rounded-lg text-white text-sm outline-none transition-colors placeholder:text-[#3f3f3f] ${!className.trim() && error ? 'border-red-500' : 'border-[#1f1f1f] focus:border-blue-500'
                        }`}
                />
            </div>

            {/* ── Section 2: Student Table ───────────────────────────────────── */}
            <div className="rounded-xl border border-gray-900 bg-gray-950/60 overflow-hidden mb-6 fade-in-d">
                {/* Table Header */}
                <div className="grid grid-cols-12 gap-2 px-5 py-3 border-b border-gray-900 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    <div className="col-span-2">Roll No *</div>
                    <div className="col-span-3">Student Name *</div>
                    <div className="col-span-3">Father Name</div>
                    <div className="col-span-3">Section</div>
                    <div className="col-span-1"></div>
                </div>

                {/* Rows */}
                {students.map((student, idx) => (
                    <div
                        key={student._key || idx}
                        className="grid grid-cols-12 gap-2 px-5 py-2 border-b border-gray-900/50 items-center hover:bg-gray-900/20 transition-colors"
                    >
                        <div className="col-span-2">
                            <input
                                type="text"
                                value={student.roll_no}
                                onChange={e => updateCell(idx, 'roll_no', e.target.value)}
                                placeholder="Roll No"
                                className={`w-full px-2.5 py-2 bg-[#0a0a0a] border rounded-lg text-white text-sm outline-none transition-colors placeholder:text-[#3f3f3f] ${hasError(idx, 'roll_no') || isDuplicate(student.roll_no)
                                        ? 'border-red-500 bg-red-500/5'
                                        : 'border-[#1f1f1f] focus:border-blue-500'
                                    }`}
                            />
                            {hasError(idx, 'roll_no') && (
                                <p className="text-red-400 text-xs mt-0.5">Required</p>
                            )}
                            {isDuplicate(student.roll_no) && (
                                <p className="text-yellow-400 text-xs mt-0.5">Duplicate</p>
                            )}
                        </div>
                        <div className="col-span-3">
                            <input
                                type="text"
                                value={student.student_name}
                                onChange={e => updateCell(idx, 'student_name', e.target.value)}
                                placeholder="Student Name"
                                className={`w-full px-2.5 py-2 bg-[#0a0a0a] border rounded-lg text-white text-sm outline-none transition-colors placeholder:text-[#3f3f3f] ${hasError(idx, 'student_name')
                                        ? 'border-red-500 bg-red-500/5'
                                        : 'border-[#1f1f1f] focus:border-blue-500'
                                    }`}
                            />
                            {hasError(idx, 'student_name') && (
                                <p className="text-red-400 text-xs mt-0.5">Required</p>
                            )}
                        </div>
                        <div className="col-span-3">
                            <input
                                type="text"
                                value={student.father_name}
                                onChange={e => updateCell(idx, 'father_name', e.target.value)}
                                placeholder="Father Name"
                                className="w-full px-2.5 py-2 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-white text-sm outline-none focus:border-blue-500 transition-colors placeholder:text-[#3f3f3f]"
                            />
                        </div>
                        <div className="col-span-3">
                            <input
                                type="text"
                                value={student.section}
                                onChange={e => updateCell(idx, 'section', e.target.value)}
                                placeholder="Section"
                                className="w-full px-2.5 py-2 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-white text-sm outline-none focus:border-blue-500 transition-colors placeholder:text-[#3f3f3f]"
                            />
                        </div>
                        <div className="col-span-1 flex justify-center">
                            <button
                                onClick={() => removeRow(idx)}
                                className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-600 hover:text-red-400 hover:bg-red-500/10 transition-all"
                                title="Remove row"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>
                    </div>
                ))}

                {/* Add Row Button */}
                <div className="px-5 py-3">
                    <button
                        onClick={addRow}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-blue-400 hover:bg-blue-500/10 border border-transparent hover:border-blue-500/30 transition-all"
                    >
                        <Plus className="w-3.5 h-3.5" />
                        Add Row
                    </button>
                </div>
            </div>

            {/* ── Section 3: Action Buttons ──────────────────────────────────── */}
            <div className="flex items-center gap-3 fade-in-d">
                {/* Hidden file input */}
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".xlsx,.xls"
                    onChange={handleFileSelect}
                    className="hidden"
                />

                <button
                    onClick={() => fileInputRef.current?.click()}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-gray-300 bg-gray-900 hover:bg-gray-800 border border-gray-800 hover:border-gray-700 transition-all"
                >
                    <Upload className="w-4 h-4" />
                    Import
                </button>

                <button
                    onClick={handleSave}
                    disabled={saving}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-bold text-white bg-blue-500 hover:bg-blue-600 disabled:bg-blue-900 disabled:cursor-not-allowed transition-all shadow-lg shadow-blue-500/20"
                >
                    {saving
                        ? <><Loader className="w-4 h-4 animate-spin" /> Saving…</>
                        : <><Save className="w-4 h-4" /> Save Class</>
                    }
                </button>
            </div>


            {/* ═══════════════════════════════════════════════════════════════════
                IMPORT MODALS
               ═══════════════════════════════════════════════════════════════════ */}

            {/* ── Column Mapping Modal ────────────────────────────────────────── */}
            {importStep === 'mapping' && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                    <div className="w-full max-w-lg rounded-xl border border-gray-800 bg-gray-950 p-6 shadow-2xl max-h-[80vh] overflow-y-auto">
                        <div className="flex items-center gap-3 mb-5">
                            <div className="w-10 h-10 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
                                <FileSpreadsheet className="w-5 h-5 text-blue-400" />
                            </div>
                            <div>
                                <h3 className="text-sm font-bold text-white">Map Columns</h3>
                                <p className="text-xs text-gray-500">Select which Excel column maps to each field</p>
                            </div>
                        </div>

                        <div className="space-y-4 mb-6">
                            {Object.keys(COLUMN_KEYWORDS).map(field => (
                                <div key={field}>
                                    <label className="block text-xs font-semibold text-gray-500 mb-1.5 uppercase tracking-wider">
                                        {fieldLabel(field)} {MANDATORY_FIELDS.includes(field) ? '*' : ''}
                                    </label>
                                    <select
                                        value={columnMapping[field] || ''}
                                        onChange={e => setColumnMapping(prev => ({
                                            ...prev,
                                            [field]: e.target.value || undefined,
                                        }))}
                                        className="w-full px-3 py-2.5 bg-[#0a0a0a] border border-[#1f1f1f] rounded-lg text-white text-sm outline-none focus:border-blue-500 transition-colors"
                                    >
                                        <option value="">— Not mapped —</option>
                                        {excelHeaders.map(h => (
                                            <option key={h} value={h}>{h}</option>
                                        ))}
                                    </select>
                                </div>
                            ))}
                        </div>

                        <div className="flex items-center gap-2 justify-end">
                            <button
                                onClick={() => { setImportStep(null); setError(null); }}
                                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs text-gray-400 hover:text-white hover:bg-gray-800 border border-gray-800 transition-all"
                            >
                                <X className="w-3.5 h-3.5" /> Cancel
                            </button>
                            <button
                                onClick={confirmMapping}
                                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs text-white bg-blue-500 hover:bg-blue-600 transition-all"
                            >
                                <CheckCircle className="w-3.5 h-3.5" /> Confirm Mapping
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ── Preview Modal ───────────────────────────────────────────────── */}
            {importStep === 'preview' && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                    <div className="w-full max-w-4xl rounded-xl border border-gray-800 bg-gray-950 p-6 shadow-2xl max-h-[85vh] overflow-y-auto">
                        <div className="flex items-center gap-3 mb-5">
                            <div className="w-10 h-10 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
                                <FileSpreadsheet className="w-5 h-5 text-blue-400" />
                            </div>
                            <div>
                                <h3 className="text-sm font-bold text-white">Preview Import</h3>
                                <p className="text-xs text-gray-500">
                                    {previewRows.filter(r => r._valid).length} valid, {previewRows.filter(r => !r._valid).length} invalid rows
                                </p>
                            </div>
                        </div>

                        {/* Preview Table */}
                        <div className="rounded-lg border border-gray-900 overflow-hidden mb-5">
                            <div className="grid grid-cols-12 gap-2 px-4 py-2 border-b border-gray-900 text-xs font-semibold text-gray-500 uppercase tracking-wider bg-gray-900/50">
                                <div className="col-span-1">Row</div>
                                <div className="col-span-2">Roll No</div>
                                <div className="col-span-3">Student Name</div>
                                <div className="col-span-2">Father Name</div>
                                <div className="col-span-2">Section</div>
                                <div className="col-span-2">Status</div>
                            </div>
                            <div className="max-h-[50vh] overflow-y-auto">
                                {previewRows.map((row, idx) => (
                                    <div
                                        key={idx}
                                        className={`grid grid-cols-12 gap-2 px-4 py-2 border-b border-gray-900/30 text-sm items-center ${row._valid ? 'text-gray-300' : 'text-red-400 bg-red-500/5'
                                            }`}
                                    >
                                        <div className="col-span-1 text-xs text-gray-600">{row._originalRow}</div>
                                        <div className="col-span-2 truncate">{row.roll_no || '—'}</div>
                                        <div className="col-span-3 truncate">{row.student_name || '—'}</div>
                                        <div className="col-span-2 truncate text-gray-500">{row.father_name || '—'}</div>
                                        <div className="col-span-2 truncate text-gray-500">{row.section || '—'}</div>
                                        <div className="col-span-2">
                                            {row._valid ? (
                                                <span className="flex items-center gap-1 text-xs text-green-400">
                                                    <CheckCircle className="w-3 h-3" /> Valid
                                                </span>
                                            ) : (
                                                <span className="flex items-center gap-1 text-xs text-red-400">
                                                    <AlertTriangle className="w-3 h-3" /> {row._reason}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="flex items-center gap-2 justify-end">
                            <button
                                onClick={() => { setImportStep(null); setError(null); }}
                                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs text-gray-400 hover:text-white hover:bg-gray-800 border border-gray-800 transition-all"
                            >
                                <X className="w-3.5 h-3.5" /> Cancel
                            </button>
                            <button
                                onClick={confirmImport}
                                disabled={previewRows.filter(r => r._valid).length === 0}
                                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs text-white bg-blue-500 hover:bg-blue-600 disabled:bg-blue-900 disabled:cursor-not-allowed transition-all"
                            >
                                <CheckCircle className="w-3.5 h-3.5" /> Confirm Import
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* ── Import Result Modal ─────────────────────────────────────────── */}
            {importStep === 'result' && importResult && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
                    <div className="w-full max-w-md rounded-xl border border-gray-800 bg-gray-950 p-6 shadow-2xl">
                        <div className="flex items-center gap-3 mb-5">
                            <div className="w-10 h-10 rounded-lg bg-green-500/15 border border-green-500/30 flex items-center justify-center">
                                <CheckCircle className="w-5 h-5 text-green-400" />
                            </div>
                            <div>
                                <h3 className="text-sm font-bold text-white">Import Complete</h3>
                                <p className="text-xs text-gray-500">Students added to the table</p>
                            </div>
                        </div>

                        <div className="space-y-2 mb-5">
                            <div className="flex items-center gap-2 text-sm">
                                <CheckCircle className="w-4 h-4 text-green-500" />
                                <span className="text-green-400">
                                    {importResult.imported} student{importResult.imported !== 1 ? 's' : ''} imported successfully
                                </span>
                            </div>

                            {importResult.skipped > 0 && (
                                <>
                                    <div className="flex items-center gap-2 text-sm">
                                        <AlertTriangle className="w-4 h-4 text-yellow-500" />
                                        <span className="text-yellow-400">
                                            {importResult.skipped} row{importResult.skipped !== 1 ? 's' : ''} skipped:
                                        </span>
                                    </div>
                                    <div className="ml-6 space-y-1">
                                        {importResult.skippedDetails.map((s, i) => (
                                            <p key={i} className="text-xs text-gray-500">
                                                — Row {s.row}: {s.reason}
                                            </p>
                                        ))}
                                    </div>
                                </>
                            )}
                        </div>

                        <p className="text-xs text-gray-600 mb-5">
                            Skipped students can be added manually using the table rows.
                        </p>

                        <div className="flex justify-end">
                            <button
                                onClick={() => { setImportStep(null); setImportResult(null); }}
                                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs text-white bg-blue-500 hover:bg-blue-600 transition-all"
                            >
                                <CheckCircle className="w-3.5 h-3.5" /> Done
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AddStudents;
