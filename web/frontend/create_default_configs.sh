#!/bin/bash

# Script to create default vulnerability configs
# Place this in the root of your project: forge/create_default_configs.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/core/configs"

# Create configs directory
mkdir -p "$CONFIG_DIR"

echo "Creating default vulnerability configs..."

# XSS Config
cat > "$CONFIG_DIR/cross_site_scripting_config.json" << 'EOF'
{
  "vulnerability_id": "xss_001",
  "name": "Cross-Site Scripting",
  "category": "cross_site_scripting",
  "difficulty_range": [1, 5],
  "description": "XSS vulnerabilities occur when untrusted data is included in a web page without proper validation or escaping. Attackers can inject malicious scripts that execute in victim's browsers.",

  "variants": [
    "Reflected XSS",
    "Stored XSS",
    "DOM-based XSS"
  ],

  "entry_points": [
    "http_get_param",
    "http_post_param",
    "url_fragment",
    "cookie_value",
    "http_header"
  ],

  "mutation_axes": {
    "filters": {
      "basic": ["script_tag", "onerror"],
      "medium": ["script_tag", "onerror", "onclick", "javascript_protocol"],
      "advanced": ["script_tag", "onerror", "onclick", "javascript_protocol", "angle_brackets", "quotes"]
    },

    "contexts": [
      "comment_section",
      "search_box",
      "user_profile",
      "message_board",
      "feedback_form"
    ],

    "sinks": [
      "innerHTML",
      "document_write",
      "eval",
      "location_href",
      "element_attribute"
    ],

    "encoding": [
      "none",
      "html_entities",
      "url_encoding",
      "base64",
      "unicode_escape"
    ],

    "output_contexts": [
      "html_body",
      "html_attribute",
      "javascript_context",
      "css_context",
      "url_context"
    ]
  },

  "variant_configs": [
    {
      "name": "Reflected XSS",
      "parameters": [
        {"name": "context", "axis": "contexts", "default": "search_box"},
        {"name": "sink", "axis": "sinks", "default": "innerHTML"},
        {"name": "output_context", "axis": "output_contexts", "default": "html_body"}
      ]
    },
    {
      "name": "Stored XSS",
      "parameters": [
        {"name": "context", "axis": "contexts", "default": "comment_section"},
        {"name": "sink", "axis": "sinks", "default": "innerHTML"},
        {"name": "storage", "axis": "storage_types", "default": "database"}
      ]
    },
    {
      "name": "DOM-based XSS",
      "parameters": [
        {"name": "context", "axis": "contexts", "default": "user_profile"},
        {"name": "sink", "axis": "sinks", "default": "location_href"}
      ]
    }
  ]
}
EOF

# SQL Injection Config
cat > "$CONFIG_DIR/sql_injection_config.json" << 'EOF'
{
  "vulnerability_id": "sqli_001",
  "name": "SQL Injection",
  "category": "sql_injection",
  "difficulty_range": [1, 5],
  "description": "SQL injection vulnerabilities occur when untrusted data is included in SQL queries without proper sanitization. Attackers can manipulate queries to access or modify database data.",

  "variants": [
    "Error-based SQLi",
    "Union-based SQLi",
    "Blind SQLi",
    "Time-based Blind SQLi"
  ],

  "entry_points": [
    "login_form",
    "search_box",
    "user_id_param",
    "product_filter",
    "api_endpoint"
  ],

  "mutation_axes": {
    "filters": {
      "basic": ["single_quote", "double_dash"],
      "medium": ["single_quote", "double_dash", "union", "select"],
      "advanced": ["single_quote", "double_dash", "union", "select", "semicolon", "comment_chars"]
    },

    "contexts": [
      "user_authentication",
      "product_search",
      "user_profile_lookup",
      "order_tracking",
      "admin_panel"
    ],

    "query_types": [
      "SELECT",
      "INSERT",
      "UPDATE",
      "DELETE"
    ],

    "injection_points": [
      "where_clause",
      "order_by",
      "limit_clause",
      "column_name"
    ]
  },

  "variant_configs": [
    {
      "name": "Error-based SQLi",
      "parameters": [
        {"name": "context", "axis": "contexts", "default": "user_authentication"},
        {"name": "query_type", "axis": "query_types", "default": "SELECT"}
      ]
    },
    {
      "name": "Union-based SQLi",
      "parameters": [
        {"name": "context", "axis": "contexts", "default": "product_search"},
        {"name": "injection_point", "axis": "injection_points", "default": "where_clause"}
      ]
    }
  ]
}
EOF

# Command Injection Config
cat > "$CONFIG_DIR/command_injection_config.json" << 'EOF'
{
  "vulnerability_id": "cmdi_001",
  "name": "Command Injection",
  "category": "command_injection",
  "difficulty_range": [1, 5],
  "description": "Command injection vulnerabilities occur when untrusted data is passed to system shell commands. Attackers can execute arbitrary system commands on the server.",

  "variants": [
    "Direct Command Injection",
    "Blind Command Injection",
    "Chained Command Injection"
  ],

  "entry_points": [
    "file_upload",
    "ping_tool",
    "dns_lookup",
    "image_processor",
    "backup_utility"
  ],

  "mutation_axes": {
    "filters": {
      "basic": ["semicolon", "pipe"],
      "medium": ["semicolon", "pipe", "ampersand", "backtick"],
      "advanced": ["semicolon", "pipe", "ampersand", "backtick", "dollar_paren", "newline"]
    },

    "contexts": [
      "network_tools",
      "file_operations",
      "system_utilities",
      "admin_tools",
      "backup_system"
    ],

    "command_types": [
      "exec",
      "system",
      "shell_exec",
      "popen",
      "subprocess"
    ]
  },

  "variant_configs": [
    {
      "name": "Direct Command Injection",
      "parameters": [
        {"name": "context", "axis": "contexts", "default": "network_tools"},
        {"name": "command_type", "axis": "command_types", "default": "system"}
      ]
    }
  ]
}
EOF

echo "✅ Created XSS config: $CONFIG_DIR/cross_site_scripting_config.json"
echo "✅ Created SQL Injection config: $CONFIG_DIR/sql_injection_config.json"
echo "✅ Created Command Injection config: $CONFIG_DIR/command_injection_config.json"
echo ""
echo "🔨 Now generating blueprints from configs..."

cd "$SCRIPT_DIR/core"

# Generate blueprints from each config
for config_file in "$CONFIG_DIR"/*_config.json; do
    if [ -f "$config_file" ]; then
        echo "Processing $(basename $config_file)..."
        python3 vuln_generator.py "$config_file"
    fi
done

echo ""
echo "✅ All default configs and blueprints created!"
echo ""
echo "You can now:"
echo "  1. Start Hackforge: ./start_hackforge.sh"
echo "  2. View configs in web UI at http://0.0.0.0:3000"
echo "  3. Generate campaigns with these blueprints"
