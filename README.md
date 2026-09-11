🛡️ OpenSquat Shield
Domain Protection & Threat Intelligence Platform
OpenSquat Shield is a cybersecurity-focused domain protection and threat intelligence platform designed to detect suspicious domains that may impersonate legitimate brands or keywords.
The project provides a web-based dashboard for scanning domains, analysing security indicators, monitoring threats, viewing analytics, and exporting scan results.
🎯 Objectives
Detect domain squatting and impersonation attempts.
Identify typosquatting, homoglyph and doppelgänger-style domains.
Perform security checks on detected domains.
Present threat information through an interactive dashboard.
Provide analytics for detected threats.
Visualize threat infrastructure on a global map.
Export scan results in JSON and CSV formats.
🔍 Key Features
1. Domain Threat Detection
OpenSquat Shield can be used to identify suspicious domains related to monitored keywords, including:
Typosquatting
Homoglyph attacks
Doppelgänger domains
Phishing-related domains
Suspicious domain variations
2. Security Checks
The dashboard includes multiple security checks:
DNS Validation – checks domain resolution using Quad9.
HTTPS Reachability – checks whether a domain is reachable through HTTPS.
Port Check – checks common web ports such as 80 and 443.
VirusTotal Check – provides an additional threat-analysis indicator when configured.
3. Interactive Dashboard
The dashboard provides:
Domains Shown
Threats Detected
Active Keywords
Total Feed Size
Scan Progress
Scan Volume
Risk Breakdown
Recent Detected Domains
Scan Activity Logs
4. Security Scans
The interface provides security monitoring options such as:
Brand Protection Daily Scan
Premium API scan mode
CT Log Listener
SSL Certificate Monitoring
Scheduled scanning
5. Threat Analytics
The Analytics section provides visual information such as:
Top Impersonated TLDs
Homoglyph vs Doppelgänger attacks
Threat/risk distribution
6. Global Threat Map
The Threat Maps section provides an interactive map for displaying infrastructure information associated with detected threats.
7. Export Results
Scan results can be exported as:
JSON
CSV
🖥️ Dashboard Sections
The web dashboard contains four main sections:
Section
Purpose
Dashboard
Overview of scans, threats and system activity
Security Scans
Security monitoring and scanning options
Analytics
Threat statistics and attack analysis
Threat Maps
Global visualization of detected threat infrastructure
🛠️ Technologies Used
Frontend
HTML5
CSS3
JavaScript
Chart.js
Leaflet.js
Backend
Python
FastAPI
Uvicorn
Pydantic
Cybersecurity / Threat Intelligence
DNS validation
HTTPS reachability checks
Port checking
VirusTotal integration
Domain squatting detection
Homoglyph detection
Phishing/threat analysis
📁 Project Structure
OpenSquatShield/
│
├── opensquat-web/
│   ├── static/
│   │   ├── index.html
│   │   ├── style.css
│   │   └── app.js
│   │
│   └── requirements.txt
│
├── opensquat/
│   └── cybersecurity and domain-analysis modules
│
├── screenshots/
│   ├── opensquat1.jpg
│   ├── opensquat2.jpg
│   ├── opensquat3.jpg
│   ├── opensquat4.jpg
│   └── opensquat5.jpg
│
├── tests/
├── README.md
├── requirements.txt
└── LICENSE
⚙️ Requirements
The web dashboard uses the following Python packages:
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
pydantic>=2.0.0
🚀 Installation
1. Clone the repository
git clone https://github.com/shobha-06/OpenSquatShield.git
cd OpenSquatShield
2. Create a virtual environment
python -m venv venv
3. Activate the virtual environment
Windows
venv\Scripts\activate
Linux / macOS
source venv/bin/activate
4. Install dependencies
pip install -r requirements.txt
If you are running the web dashboard separately, install its web requirements:
pip install -r opensquat-web/requirements.txt
▶️ Running the Project
The exact FastAPI entry-point filename depends on the backend file used in the local project.
For a FastAPI application exposed as app in main.py, use:
uvicorn main:app --reload
Then open the local address shown by Uvicorn in your browser.
🔄 How It Works
The basic workflow of OpenSquat Shield is:
User Keywords
      ↓
Domain Generation / Detection
      ↓
Suspicious Domain Identification
      ↓
Security Checks
      ↓
Threat Analysis
      ↓
Dashboard Visualization
      ↓
Export Results
📸 Screenshots
Dashboard
�
Security Scans
�
Analytics
�
Threat Map
�
Scan Results / Activity
�
🔐 Security Note
API keys and other credentials should never be committed to a public GitHub repository.
Use environment variables or another secure configuration method for real API keys.
Example:
VIRUSTOTAL_API_KEY=your_api_key_here
Do not publish real API keys inside source code, screenshots, README.md, or configuration files.
🔮 Future Scope
Possible future improvements include:
Automated scheduled scans
Email or notification alerts
More threat-intelligence feeds
Improved phishing detection
Machine-learning-based domain classification
Advanced threat scoring
More detailed historical analytics
Improved authentication and role-based access
Cloud deployment
Continuous domain monitoring
🎓 Project Purpose
OpenSquat Shield was developed as a cybersecurity academic project to demonstrate practical concepts related to:
Domain security
Threat intelligence
Brand protection
Phishing detection
DNS and network security
Security monitoring
Data visualization
👩‍💻 Author
Shobha
BCA Student
Cybersecurity Project
GitHub: https://github.com/shobha-06
⚠️ Disclaimer
This project is intended for educational, research, and authorized security-monitoring purposes only.
Do not use the project to scan or monitor systems, domains, or infrastructure without proper authorization.
📄 License
This project follows the license included in the repository.