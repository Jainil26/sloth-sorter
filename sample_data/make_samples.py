"""Generates 30 realistic sample documents (.txt and .docx) for demonstrating and benchmarking sloth-sorter's Tier 2 smart pipeline."""

import json
from pathlib import Path
from typing import Dict, Tuple
import docx

SAMPLES_DATA = [
    # Invoices (6 files)
    (
        "doc_8192.txt",
        "Invoices",
        "txt",
        (
            "Acme Cloud Services - Monthly Billing Statement\n"
            "Invoice Number: INV-2024-0892\n"
            "Billing Period: March 1, 2024 - March 31, 2024\n"
            "Customer ID: CUST-449102\n\n"
            "Description: High Performance Compute Instances & Cloud Storage\n"
            "Subtotal: $135.00\n"
            "Sales Tax (8.25%): $11.14\n"
            "Total Amount Due: $146.14\n"
            "Payment Due Date: April 15, 2024\n"
            "Please remit payment via wire transfer or online portal."
        ),
    ),
    (
        "billing_statement_04.docx",
        "Invoices",
        "docx",
        (
            "Pacific Electric & Power Utility Bill\n"
            "Account Number: 9948-2810-12\n"
            "Statement Date: April 4, 2024\n"
            "Customer: Jane Doe, 124 Main Street\n\n"
            "Monthly electricity service charge: $74.20\n"
            "Grid distribution fee: $14.50\n"
            "Total Balance Due: $88.70\n"
            "Payment Due Date: April 25, 2024\n"
            "Thank you for being a valued customer. Autopay scheduled."
        ),
    ),
    (
        "vendor_inv.txt",
        "Invoices",
        "txt",
        (
            "Invoice for Freelance Consulting Services\n"
            "Invoice #2024-104\n"
            "Billed To: Apex Innovations LLC\n"
            "Services Rendered: Python backend development and API performance tuning\n"
            "Hours Worked: 30 hours @ $95/hr\n"
            "Total Amount: $2,850.00\n"
            "Payment terms: Net 30 days. Direct bank deposit preferred."
        ),
    ),
    (
        "statement_apr.docx",
        "Invoices",
        "docx",
        (
            "Office Supply Depot - Commercial Sales Receipt & Tax Invoice\n"
            "Order ID: ORD-99214\n"
            "Items Purchased: Ergonomic Mesh Chairs (x2), Standing Desk Converter\n"
            "Subtotal: $480.00\n"
            "Tax: $38.40\n"
            "Grand Total: $518.40\n"
            "Payment Status: Paid in full via Visa ending in 4092."
        ),
    ),
    (
        "export_3910.txt",
        "Invoices",
        "txt",
        (
            "Metro Water and Sanitation Utility Invoice\n"
            "Customer Account: 401-291-88\n"
            "Billing Cycle: February 15 - March 15, 2024\n"
            "Water consumption: 3,200 gallons\n"
            "Current Charges: $46.80\n"
            "Overdue Balance: $0.00\n"
            "Total Due: $46.80. Pay before April 10, 2024."
        ),
    ),
    (
        "invoice_mar.docx",
        "Invoices",
        "docx",
        (
            "Hardware Server Hosting Co - Final Billing Statement\n"
            "Invoice #883912\n"
            "Dedicated Bare-Metal Server monthly lease and 10Gbps transit\n"
            "Total Amount Due: $350.00\n"
            "Due Upon Receipt. Remit to accounts@hostingco.com."
        ),
    ),

    # Resumes (6 files)
    (
        "profile_summary.docx",
        "Resumes",
        "docx",
        (
            "Jane Doe - Staff Software Engineer\n"
            "San Francisco, CA | jane.doe@example.com | github.com/janedoe\n\n"
            "Professional Summary:\n"
            "Results-driven software architect with 8+ years experience designing "
            "low-latency distributed systems and scalable cloud infrastructure.\n\n"
            "Work Experience:\n"
            "- Senior Software Engineer, Google (2020 - Present): Lead engineer for core indexing pipeline.\n"
            "- Software Engineer, Uber (2017 - 2020): Scaled microservices handling 2M requests/sec.\n\n"
            "Education:\n"
            "B.S. in Computer Science, Stanford University (2017)\n"
            "Technical Skills: Python, Go, Rust, Kubernetes, Distributed Systems, Redis."
        ),
    ),
    (
        "candidate_39.txt",
        "Resumes",
        "txt",
        (
            "Curriculum Vitae: Alex Rivera\n"
            "Data Science and Machine Learning Engineer\n\n"
            "Work History:\n"
            "Machine Learning Specialist at Quant Analytics (2021-2024)\n"
            "Developed predictive models and NLP classification pipelines achieving 94% accuracy.\n"
            "Junior Data Analyst at FinTech Corp (2019-2021)\n\n"
            "Education:\n"
            "M.S. in Data Science, University of California Berkeley\n"
            "Core Competencies: Machine Learning, PyTorch, Scikit-learn, SQL, Statistics."
        ),
    ),
    (
        "cv_jdoe.docx",
        "Resumes",
        "docx",
        (
            "Michael Chang - Principal DevOps & Site Reliability Engineer\n"
            "Career Overview:\n"
            "Over 10 years automating CI/CD pipelines, container orchestration, and cloud reliability.\n\n"
            "Employment History:\n"
            "- Lead SRE, Cloudflare (2019 - 2024): Maintained 99.999% uptime for global DNS infrastructure.\n"
            "- Infrastructure Engineer, Spotify (2015 - 2019): Managed AWS Terraform deployments.\n\n"
            "Education & Certifications:\n"
            "B.S. Computer Engineering, University of Washington\n"
            "AWS Certified Solutions Architect Professional, CKA."
        ),
    ),
    (
        "applicant_doc.txt",
        "Resumes",
        "txt",
        (
            "Sarah Jenkins - Product Designer & UI/UX Specialist\n"
            "Portfolio: sarahjdesign.com | email: sarah@design.io\n\n"
            "Experience:\n"
            "Senior Product Designer at Airbnb (2021 - Present)\n"
            "Led redesign of host booking workflow, improving conversion rate by 18%.\n"
            "UI Designer at Lyft (2018 - 2021)\n\n"
            "Education:\n"
            "B.F.A. in Graphic Design & Interaction, Rhode Island School of Design\n"
            "Skills: Figma, User Research, Prototyping, Wireframing, Usability Testing."
        ),
    ),
    (
        "resume_draft.docx",
        "Resumes",
        "docx",
        (
            "David Patel - Frontend Software Developer\n"
            "Technical Skills: React, Next.js, TypeScript, TailwindCSS, WebSockets\n\n"
            "Experience Summary:\n"
            "Frontend Engineer at Stripe (2022-2024): Built checkout dashboards and analytics UI.\n"
            "Web Developer at Shopify (2020-2022): Developed responsive merchant storefronts.\n\n"
            "Education:\n"
            "B.S. in Computer Science, University of Toronto."
        ),
    ),
    (
        "bio_workhistory.txt",
        "Resumes",
        "txt",
        (
            "Curriculum Vitae: Emily Watson\n"
            "Product Manager & Technical Lead\n\n"
            "Professional Background:\n"
            "Senior Product Manager at Microsoft (2019 - Present)\n"
            "Owned developer platform roadmap and delivered developer CLI tools used by 500k developers.\n"
            "Associate PM at Atlassian (2017 - 2019)\n\n"
            "Education:\n"
            "MBA, Harvard Business School; B.S. Electrical Engineering, MIT."
        ),
    ),

    # Assignments (6 files)
    (
        "problem_set_2.txt",
        "Assignments",
        "txt",
        (
            "CS 161: Design and Analysis of Algorithms\n"
            "Problem Set 2: Divide-and-Conquer and Dynamic Programming\n"
            "Due Date: Friday, October 27, 2024 at 11:59 PM PST\n\n"
            "Submission Instructions: Submit code and LaTeX solution PDF via Gradescope.\n"
            "Problem 1 (25 pts): Prove the recurrence relation T(n) = 3T(n/2) + O(n) using Master Theorem.\n"
            "Problem 2 (35 pts): Design an O(n log n) algorithm to compute the maximum subarray product.\n"
            "Problem 3 (40 pts): Implement the dynamic programming knapsack algorithm."
        ),
    ),
    (
        "cs106_hw.docx",
        "Assignments",
        "docx",
        (
            "CS 106B Programming Assignment 3: Recursive Backtracking & Mazes\n"
            "Course Instructor: Prof. Roberts\n"
            "Student Submission Deadline: November 3, 2024\n\n"
            "Assignment Objectives:\n"
            "1. Implement a recursive depth-first maze solver.\n"
            "2. Generate all valid subsets matching a target sum.\n"
            "Grading Rubric:\n"
            "- Correctness & unit tests: 60%\n"
            "- Code style and recursion efficiency: 40%\n"
            "Please include your test outputs in your submission archive."
        ),
    ),
    (
        "lab_exercise_4.txt",
        "Assignments",
        "txt",
        (
            "Operating Systems Lab Assignment 4: Virtual Memory & Page Replacement\n"
            "Due: October 30, 2024\n"
            "Lab Exercise Deliverables:\n"
            "Write a C program that simulates FIFO, LRU, and Optimal page replacement algorithms.\n"
            "Measure page fault rates on varying memory frame allocations.\n"
            "Submit your lab report and source code to the university portal."
        ),
    ),
    (
        "assignment_ml.docx",
        "Assignments",
        "docx",
        (
            "Machine Learning Coursework Assignment 1\n"
            "Supervised Learning: Logistic Regression and Decision Trees\n"
            "Due Date: November 12, 2024\n\n"
            "Instructions:\n"
            "Train baseline classifiers on the benchmark dataset.\n"
            "Evaluate precision, recall, and F1-score across 5-fold cross validation.\n"
            "Write a 3-page assignment report explaining hyperparameters and loss curves."
        ),
    ),
    (
        "homework_math.txt",
        "Assignments",
        "txt",
        (
            "MATH 215: Linear Algebra Homework Assignment 6\n"
            "Due: Wednesday at the start of class.\n"
            "Questions:\n"
            "1. Find eigenvalues and eigenvectors for the given 3x3 symmetric matrix.\n"
            "2. Determine whether the vector space is orthogonal under the standard inner product.\n"
            "3. Show all work and steps clearly for full credit."
        ),
    ),
    (
        "coursework_sub.docx",
        "Assignments",
        "docx",
        (
            "Database Systems Course Project Assignment: Schema Design & Normalization\n"
            "Deliverables:\n"
            "- Entity-Relationship (ER) diagram in 3NF.\n"
            "- SQL DDL scripts creating tables with foreign key constraints.\n"
            "- Query benchmark report measuring execution times with B-tree indexes."
        ),
    ),

    # Reports (6 files)
    (
        "quarterly_review.docx",
        "Reports",
        "docx",
        (
            "Q3 2024 Corporate Financial and Operational Performance Report\n"
            "Executive Summary:\n"
            "During the third quarter, consolidated revenue reached $42.5 million, "
            "representing an 18% year-over-year growth rate across all business units.\n\n"
            "Market Analysis & Competitive Landscape:\n"
            "Enterprise subscription retention remained strong at 112% net retention.\n"
            "Gross margins expanded by 210 basis points due to cloud infrastructure optimizations.\n\n"
            "Conclusion & Outlook for Q4:\n"
            "Management maintains full-year guidance and projects sustained profitability."
        ),
    ),
    (
        "q3_financial_exec.txt",
        "Reports",
        "txt",
        (
            "Annual Business Performance Evaluation Report\n"
            "Fiscal Year 2024 Executive Overview\n\n"
            "Key Findings:\n"
            "1. Customer acquisition costs decreased by 22% following inbound marketing automation.\n"
            "2. Operating cash flows reached record highs of $18.4 million.\n"
            "3. Strategic acquisitions expanded addressable European market share.\n\n"
            "Recommendations for executive leadership regarding 2025 capital expenditures."
        ),
    ),
    (
        "audit_findings.docx",
        "Reports",
        "docx",
        (
            "Independent Cybersecurity Audit & Compliance Report\n"
            "Audit Scope: Internal Network Architecture and Access Control Policies\n\n"
            "Executive Summary:\n"
            "The security audit conducted between Sept 1 and Sept 20 evaluated SOC2 Type II controls.\n"
            "Assessment Findings:\n"
            "- Multi-factor authentication is 100% adopted.\n"
            "- Automated vulnerability scanning remediates high-severity findings in under 48 hours.\n"
            "Conclusion: Compliance standards satisfactorily met."
        ),
    ),
    (
        "market_assessment.txt",
        "Reports",
        "txt",
        (
            "Market Research Investigation Report: Cloud Native Storage Trends\n"
            "Published by Tech Horizon Research Group\n\n"
            "Market Dynamics:\n"
            "The Kubernetes data storage ecosystem is expanding at 28% CAGR.\n"
            "Survey results indicate 72% of enterprises prioritize local NVMe replication.\n"
            "Detailed market forecast, pricing analysis, and competitive positioning report."
        ),
    ),
    (
        "security_eval.docx",
        "Reports",
        "docx",
        (
            "Technical Evaluation Report: Cloud Database Migration Feasibility\n"
            "Report Prepared for: Technology Steering Committee\n\n"
            "Analysis:\n"
            "Benchmarked latency, throughput, and failover capabilities between self-hosted Postgres and AWS Aurora.\n"
            "Results indicate 30% reduction in database maintenance overhead with zero data loss.\n"
            "Final migration recommendations and execution plan."
        ),
    ),
    (
        "annual_perf.txt",
        "Reports",
        "txt",
        (
            "Annual Environmental Sustainability and ESG Report\n"
            "Company Sustainability Metrics for 2024\n\n"
            "Key Performance Indicators:\n"
            "1. 40% reduction in data center carbon footprint using renewable power agreements.\n"
            "2. Zero electronic waste sent to landfills.\n"
            "Full report detailing audit methodologies and environmental milestones."
        ),
    ),

    # Study Material (6 files)
    (
        "lecture_07_dist_sys.txt",
        "Study Material",
        "txt",
        (
            "Lecture 7: Consensus in Distributed Systems\n"
            "Course: Distributed Computing Systems\n"
            "Reading: Chapter 5 of Distributed Systems Textbook\n\n"
            "Topics Covered:\n"
            "1. Two-phase commit vs three-phase commit protocols.\n"
            "2. Paxos consensus algorithm: proposers, acceptors, learners.\n"
            "3. Raft consensus: leader election, log replication, and safety guarantees.\n"
            "Study questions and key concepts review for upcoming midterm exam."
        ),
    ),
    (
        "syllabus_intro_dl.docx",
        "Study Material",
        "docx",
        (
            "Course Syllabus & Study Guide: Introduction to Deep Learning\n"
            "Instructor: Dr. Alan Turing | Fall Semester\n\n"
            "Course Overview:\n"
            "This course covers modern neural network architectures including CNNs, RNNs, and Transformers.\n\n"
            "Recommended Textbooks:\n"
            "- Deep Learning by Goodfellow, Bengio, Courville\n"
            "Exam Schedule:\n"
            "- Midterm Examination: Week 8\n"
            "- Final Project Presentation: Week 15\n"
            "Weekly lecture reading materials and slide deck links."
        ),
    ),
    (
        "biology_ch4_review.txt",
        "Study Material",
        "txt",
        (
            "Cellular Biology Study Guide: Chapter 4 Cellular Respiration\n"
            "Exam Revision Notes & Summary:\n"
            "1. Glycolysis: Glucose breakdown into pyruvate in cytoplasm, generating 2 ATP.\n"
            "2. Krebs Citric Acid Cycle: Mitochondrial matrix oxidation producing NADH and FADH2.\n"
            "3. Electron Transport Chain: Oxidative phosphorylation generating proton gradient.\n"
            "Key definitions, formulas, and flashcard practice questions."
        ),
    ),
    (
        "comp_arch_slides.docx",
        "Study Material",
        "docx",
        (
            "Computer Architecture Lecture Slides: Memory Hierarchy & Cache Design\n"
            "Course Study Notes\n\n"
            "Slide Overview:\n"
            "- L1, L2, L3 cache organization, associativity, and replacement policies.\n"
            "- Cache miss classification: Compulsory, Capacity, Conflict (The 3 Cs).\n"
            "- Virtual memory translation lookaside buffer (TLB) operation.\n"
            "Practice problem walkthroughs for exam preparation."
        ),
    ),
    (
        "exam_revision_notes.txt",
        "Study Material",
        "txt",
        (
            "Macroeconomics Final Exam Revision Study Notes\n"
            "Key Concepts & Formulas Guide:\n"
            "- IS-LM model: Goods market and money market equilibrium.\n"
            "- Phillips curve relationship between inflation and unemployment.\n"
            "- Fiscal vs monetary policy transmission mechanisms.\n"
            "Review questions, formula sheet, and chapter outline."
        ),
    ),
    (
        "lecture_notes_econ.docx",
        "Study Material",
        "docx",
        (
            "Organic Chemistry Lecture Notes: Nucleophilic Substitution Reactions\n"
            "Course Study Material\n\n"
            "Lecture Summary:\n"
            "- SN1 vs SN2 reaction mechanisms: kinetics, stereochemistry, solvent effects.\n"
            "- Carbocation stability, leaving group ability, and nucleophile strength.\n"
            "Summary table and textbook practice problem solutions."
        ),
    ),
]


def generate_samples(output_dir: Path) -> Dict[str, str]:
    """Generate sample files in output_dir and return a ground-truth mapping."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ground_truth = {}

    for filename, category, file_type, content in SAMPLES_DATA:
        file_path = output_dir / filename
        if file_type == "txt":
            file_path.write_text(content, encoding="utf-8")
        elif file_type == "docx":
            doc = docx.Document()
            # Split lines into paragraphs
            for line in content.split("\n"):
                doc.add_paragraph(line)
            doc.save(str(file_path))

        ground_truth[filename] = category

    # Also save ground_truth.json alongside samples
    labels_file = output_dir / "ground_truth.json"
    with open(labels_file, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    return ground_truth


if __name__ == "__main__":
    out = Path("sample_data/samples").resolve()
    print(f"Generating 30 realistic samples in {out}...")
    gt = generate_samples(out)
    print(f"Successfully generated {len(gt)} samples across 5 categories.")
