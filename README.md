# Non-Destructive Vulnerability Scanner v2.0

A comprehensive, production-safe security testing tool for web applications with **intelligent crawling** and **API endpoint discovery**. This scanner performs non-destructive vulnerability assessments covering multiple attack vectors and security misconfigurations.

## ⚠️ Important Notice

**This tool is designed for AUTHORIZED testing only.** Only use this scanner on:
- Websites you own
- Websites you have explicit written permission to test
- Your production environments for security auditing

Unauthorized security testing may be illegal in your jurisdiction.

## 🔍 Features

### 🕷️ Intelligent Web Crawler
- **Automatic endpoint discovery** - Crawls your website to find all accessible pages
- **API route detection** - Discovers REST APIs, GraphQL endpoints, and API documentation
- **JavaScript analysis** - Extracts API endpoints from JS files
- **Form discovery** - Identifies all forms for CSRF and input validation testing
- **Configurable depth & limits** - Control crawl scope with depth and URL limits

### 📄 API Client File Import
- **Static parsing** of your frontend API client file (e.g. `api.js`)
- Extracts routes like `api.get('/users')` and `api.post('/auth/login')`
- Automatically prefixes routes with the client `baseURL` (defaults to `/api`)
- Adds imported endpoints into API security tests

### Comprehensive Vulnerability Detection

#### 1. **SSL/TLS Security**
- Protocol version validation (TLS 1.2+)
- Certificate verification
- Cipher suite analysis
- Detection of deprecated protocols (SSLv3, TLSv1.0, TLSv1.1)

#### 2. **Security Headers Analysis**
- Strict-Transport-Security (HSTS)
- X-Frame-Options
- X-Content-Type-Options
- Content-Security-Policy (CSP)
- X-XSS-Protection
- Referrer-Policy
- Permissions-Policy

#### 3. **Injection Vulnerabilities**
- **Cross-Site Scripting (XSS)**: Reflected XSS detection
- **SQL Injection**: Error-based SQLi detection for MySQL, PostgreSQL, MSSQL, Oracle
- **Command Injection**: OS command injection testing
- **Directory Traversal**: Path traversal vulnerability detection

#### 4. **Authentication & Session Security**
- CSRF token validation
- Cookie security attributes (Secure, HttpOnly, SameSite)
- Session management analysis

#### 5. **Access Control Issues**
- Clickjacking protection testing
- CORS misconfiguration detection
- HTTP methods validation (PUT, DELETE, TRACE)
- Open redirect vulnerabilities

#### 6. **Information Disclosure**
- Sensitive file exposure (.git, .env, config files)
- Server/technology fingerprinting
- Error message analysis
- Subdomain takeover detection

#### 7. **API Security Testing**
- **Common API endpoint discovery** - Tests for /api, /graphql, /swagger, etc.
- **GraphQL introspection** - Detects exposed GraphQL schemas
- **API authentication testing** - Checks for unauthenticated API access
- **HTTP method testing** - Validates dangerous methods (PUT, DELETE, PATCH)
- **Rate limiting detection** - Tests for API rate limiting
- **API documentation exposure** - Detects exposed Swagger/OpenAPI docs

#### 8. **Enhanced Endpoint Testing**
- **Parameter-based XSS** - Tests all discovered URL parameters for XSS
- **Parameter-based SQLi** - Tests URL parameters for SQL injection
- **JavaScript secret scanning** - Searches JS files for API keys, tokens, passwords
- **Form-based vulnerability testing** - Tests all discovered forms

## 📋 Requirements

- Python 3.7+
- Internet connection
- Target website URL

## 🚀 Installation

1. **Clone or download the scanner:**
```bash
cd /path/to/scanner
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Make the script executable (optional):**
```bash
chmod +x vulnerability_scanner.py
```

## 💻 Usage

### Basic Scan (with crawler)
```bash
python3 vulnerability_scanner.py -u https://example.com
```

### Verbose Mode (Detailed Output)
```bash
python3 vulnerability_scanner.py -u https://example.com -v
```

### Export Results to JSON
```bash
python3 vulnerability_scanner.py -u https://example.com -o report.json
```

### Import endpoints from your frontend API file
```bash
python3 vulnerability_scanner.py -u https://example.com --api-file ./api.js
```

### Quick Scan (No Crawler)
```bash
python3 vulnerability_scanner.py -u https://example.com --no-crawl
```

### Deep Crawl with Custom Settings
```bash
python3 vulnerability_scanner.py -u https://example.com -d 3 -m 100 -v
```

### Complete Example
```bash
python3 vulnerability_scanner.py -u https://example.com -v -t 20 -d 2 -m 50 --api-file ./api.js -o security_report.json
```

# Full scan (recommended)
python3 vulnerability_scanner.py -u https://example.com --api-file ./api.js -v -o report.json

# Slower/stealthier (avoids WAF rate limiting)
python3 vulnerability_scanner.py -u https://example.com --api-file ./api.js --delay 0.5 -v -o report.json

# No crawler, just API file + core tests
python3 vulnerability_scanner.py -u https://example.com --no-crawl --api-file ./api.js -v -o report.json


## 📊 Command Line Arguments

| Argument | Short | Description | Required | Default |
|----------|-------|-------------|----------|---------|
| `--url` | `-u` | Target URL to scan | Yes | - |
| `--verbose` | `-v` | Enable verbose output | No | False |
| `--timeout` | `-t` | Request timeout (seconds) | No | 10 |
| `--output` | `-o` | Export JSON report file | No | - |
| `--no-crawl` | - | Disable crawler (faster scan) | No | False |
| `--depth` | `-d` | Crawler depth level | No | 2 |
| `--max-urls` | `-m` | Maximum URLs to crawl | No | 50 |
| `--api-file` | - | Path to a local JS/TS API client file to import endpoints from | No | - |

## 📈 Understanding Results

### Severity Levels

- **🔴 CRITICAL**: Immediate action required - severe security risk
  - Examples: SQL Injection, Command Injection, Subdomain Takeover
  
- **🔴 HIGH**: High priority - significant security vulnerability
  - Examples: XSS, Directory Traversal, Missing HTTPS
  
- **🟡 MEDIUM**: Should be addressed - moderate security concern
  - Examples: Missing CSRF tokens, CORS misconfiguration, Missing HSTS
  
- **🟡 LOW**: Best practice improvement
  - Examples: Missing security headers, Information disclosure

### Sample Output

```
======================================================================
  Non-Destructive Vulnerability Scanner v2.0
======================================================================

Target: https://example.com
Started: 2026-03-05 08:50:00

[08:50:01] INFO - Testing SSL/TLS Configuration...
[08:50:02] INFO - Testing Security Headers...
[08:50:03] VULN - Security Headers: HSTS header missing
[08:50:04] INFO - Testing for XSS Vulnerabilities...
...

======================================================================
  SCAN REPORT
======================================================================

Summary:
  CRITICAL: 0
  HIGH: 2
  MEDIUM: 5
  LOW: 3
  WARNINGS: 4

HIGH SEVERITY VULNERABILITIES:
  • [XSS] Potential Reflected XSS vulnerability detected
    Details: Payload reflected in response: <script>alert(1)</script>
  • [Information Disclosure] Sensitive file accessible: /.env
    Details: Status code: 200
...
```

## 🔒 Safety Features

This scanner is designed to be **non-destructive**:

✅ **Read-only operations** - No data modification
✅ **No brute force** - Limited request attempts
✅ **Safe payloads** - Test strings that don't cause harm
✅ **Timeout protection** - Prevents hanging requests
✅ **Production-safe** - Can be run on live websites

## 🧭 Selenium Test Suite (RMS)

Heuristic, role-aware Selenium tests for the RMS web app. Only the **Admin** account needs credentials; other roles are auto-generated during the run.

## Prerequisites
- Python 3.9+
- Chrome/Firefox/Edge installed (one is enough)
- `pip install -r requirements.txt`
- Admin credentials for RMS

## Configure
1) Open `rms_test_config.json`
2) Set only:
   - `roles["Admin"].credentials.username`
   - `roles["Admin"].credentials.password`
   - (optional) `email`
3) Leave other roles empty; the suite generates them.

## Run
```bash
# Basic (Chrome)
python rms_selenium_test.py --url http://localhost:8000

# Headless
python rms_selenium_test.py --url http://localhost:8000 --headless

# Specific roles
python rms_selenium_test.py --url http://localhost:8000 --roles admin,teacher

# Skip destructive POST/PUT/DELETE
python rms_selenium_test.py --url http://localhost:8000 --skip-destructive
```

Common flags:
- `--browser chrome|firefox|edge` (default: chrome)
- `--headless` (run without UI)
- `--roles role1,role2` (filter roles)
- `--delay 1.0` (seconds between actions; default 0.5)
- `--output <dir>` (reports directory; default `rms_test_results`)

## What the suite does
1) Pre-auth checks (login page, rate limiting, CSRF/HTTP methods)
2) Unauthenticated API/CSRF tests
3) Admin login → provision generated role accounts (best-effort UI creation; otherwise uses generated creds)
4) Per-role login → RBAC, web/API/security tests
5) Report generation

## Outputs
- `rms_test_results/`
  - `rms_test_report.json`
  - `rms_test_report.html`
  - `test_run.log`
  - `screenshots/`

## Safety
- `--skip-destructive` avoids destructive POST/PUT/DELETE.
- Provisioning tries common admin user-add pages; specify your exact admin user-create path/fields for higher reliability.

## 🎯 What Gets Tested

### Network Layer
- SSL/TLS configuration
- Certificate validation
- Protocol versions

### Application Layer
- HTTP security headers
- Cookie security
- CORS policies
- HTTP methods

### Input Validation
- XSS vulnerabilities
- SQL injection
- Command injection
- Path traversal

### Access Control
- CSRF protection
- Clickjacking protection
- Open redirects

### Information Security
- Sensitive file exposure
- Server fingerprinting
- Error handling

## 📝 JSON Report Format

When using `-o` flag, the scanner generates a detailed JSON report:

```json
{
  "target": "https://example.com",
  "scan_time": "2026-03-05T08:50:00",
  "vulnerabilities": [
    {
      "category": "XSS",
      "severity": "HIGH",
      "description": "Potential XSS vulnerability",
      "details": "Payload reflected in response",
      "timestamp": "2026-03-05T08:50:05"
    }
  ],
  "warnings": [...],
  "info": [...],
  "summary": {
    "critical": 0,
    "high": 2,
    "medium": 5,
    "low": 3
  }
}
```

## 🛠️ Troubleshooting

### SSL Certificate Errors
If you encounter SSL verification errors:
- The scanner automatically handles self-signed certificates
- Check if the target uses valid SSL/TLS

### Timeout Issues
If requests are timing out:
```bash
python vulnerability_scanner.py -u https://example.com -t 30
```

### Connection Refused
- Verify the URL is correct and accessible
- Check if the website is behind a firewall
- Ensure you have internet connectivity

## 🔧 Advanced Usage

### Testing Specific Subdomains
```bash
python vulnerability_scanner.py -u https://api.example.com
python vulnerability_scanner.py -u https://admin.example.com
```

### Automated Scanning (Cron Job)
```bash
# Daily scan at 2 AM
0 2 * * * /usr/bin/python3 /path/to/vulnerability_scanner.py -u https://example.com -o /var/log/security/scan_$(date +\%Y\%m\%d).json
```

## 📚 Best Practices

1. **Schedule Regular Scans**: Run weekly or after major deployments
2. **Review All Findings**: Not all warnings are critical, but all should be reviewed
3. **Prioritize Fixes**: Address CRITICAL and HIGH severity issues first
4. **Keep Records**: Save JSON reports for compliance and tracking
5. **Retest After Fixes**: Verify vulnerabilities are properly remediated
6. **Combine with Other Tools**: Use alongside penetration testing and code reviews

## ⚡ Performance

- **Average scan time**: 30-60 seconds
- **Request rate**: Non-aggressive (production-safe)
- **Resource usage**: Minimal CPU and memory footprint

## 🚫 Limitations

This scanner is designed for **initial assessment** and does not replace:
- Professional penetration testing
- Manual security code review
- Authenticated vulnerability scanning
- Deep application logic testing
- Business logic vulnerability testing

## 📖 Vulnerability Categories Explained

### Cross-Site Scripting (XSS)
Allows attackers to inject malicious scripts into web pages viewed by other users.

### SQL Injection
Enables attackers to interfere with database queries, potentially accessing or modifying data.

### Command Injection
Allows execution of arbitrary operating system commands on the server.

### Directory Traversal
Permits access to files outside the intended directory structure.

### CSRF (Cross-Site Request Forgery)
Tricks users into performing unwanted actions on authenticated sessions.

### Clickjacking
Overlays invisible frames to trick users into clicking malicious content.

### CORS Misconfiguration
Improper Cross-Origin Resource Sharing settings that may expose sensitive data.

## 🤝 Contributing

To extend the scanner with additional tests:

1. Add new test methods following the pattern:
```python
def test_new_vulnerability(self):
    """Test for new vulnerability type"""
    self.log("Testing New Vulnerability...", "INFO")
    # Test logic here
    # Use self.add_vulnerability() for findings
```

2. Register the test in `run_scan()` method

## 📄 License

This tool is provided as-is for security testing purposes. Use responsibly and legally.

## 🆘 Support

For issues or questions:
1. Review this README thoroughly
2. Check the troubleshooting section
3. Verify you have the latest version
4. Ensure all dependencies are installed

## 🔄 Version History

- **v1.0.0** (2026-03-05): Initial release
  - 14 vulnerability test categories
  - JSON export functionality
  - Color-coded terminal output
  - Non-destructive testing approach

# Record your login session first
python3 rms_pattern_recorder.py --url http://test.localhost:8000

# Then run the auditor with the pattern
python3 rms_autonomous_agent.py --url http://test.localhost:8000 --pattern ui_pattern.json

# With visual debug (red border on each element)
python3 rms_autonomous_agent.py --url http://test.localhost:8000 --pattern ui_pattern.json --visual-debug

---

**Remember**: Always obtain proper authorization before testing any website. Unauthorized security testing may violate laws and terms of service.


