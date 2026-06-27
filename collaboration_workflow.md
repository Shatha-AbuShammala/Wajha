# Wajha Team Collaboration & Git Workflow Guide

This guide details how to split roles, work together using Git, and set up protections to prevent teammates from breaking the `main` branch.

---

## 1. How to Divide the Work (Roles & Responsibilities)

Because Wajha is split into 5 distinct Django apps, you can assign features to team members based on their interests and strengths:

### 👤 Developer A: Auth & UX Architect
*   **Primary App:** `accounts` (and base templates)
*   **Tasks:**
    *   Set up Django custom user models and authentication (registration, login, logout, password resets).
    *   Build student profile setup pages (GPA, field of study, CV file uploads).
    *   Establish the base HTML template, layout, navigation bar, and styling using Bootstrap 5.

### 👤 Developer B: Database & Search Specialist
*   **Primary App:** `grants`
*   **Tasks:**
    *   Write the database models for scholarships and tags.
    *   Create search and filter logic (allowing users to filter by degree level, country, field of study).
    *   Build the admin CRUD views and dashboards to manage scholarship posts.

### 👤 Developer C: Scraper & Automation Engineer
*   **Primary App:** `scrapers`
*   **Tasks:**
    *   Write BeautifulSoup or Scrapy crawler scripts to fetch data from scholarship websites.
    *   Set up task schedules (Celery or background django commands) to trigger scrapers automatically.
    *   Create the admin review page to preview scraped data before publishing it.

### 👤 Developer D: AI Engineer & Flow Coordinator
*   **Primary Apps:** `ai_engine` & `applications`
*   **Tasks:**
    *   Integrate the Anthropic SDK to call the Claude API.
    *   Develop AI prompts for matching scholarships, summarising eligibility criteria, and drafting motivation letters.
    *   Build the application tracking dashboard (saved, pending, submitted) and deadline alerts.

---

## 2. How to Work Together (The Daily Workflow)

To avoid code conflicts (merge issues), follow the **GitHub Flow** cycle for every single task:

```
  [main branch] ───────► (Create Branch) ───────► [feature/login-page]
       ▲                                                 │
       │                                                 ▼
       │                                            (Write Code)
       │                                                 │
       │                                                 ▼
       │                                           (Commit & Push)
       │                                                 │
       │                                                 ▼
  (Merge PR) ◄───────── (Approve PR) ◄────────── (Pull Request)
```

1.  **Sync Local Repository:** Before starting any work, pull the latest code from GitHub:
    ```bash
    git checkout main
    git pull origin main
    ```
2.  **Create a Feature Branch:** Never work on `main`. Create a new branch named after your task:
    ```bash
    git checkout -b feature/add-login-form
    ```
3.  **Code and Save:** Write your code, then save your progress locally:
    ```bash
    git add .
    git commit -m "feat: design login page template and route"
    ```
4.  **Push to GitHub:** Upload your branch to GitHub:
    ```bash
    git push origin feature/add-login-form
    ```
5.  **Open a Pull Request (PR):** Go to GitHub, click "Compare & pull request", describe your changes, and assign a teammate to review it.
6.  **Review and Merge:** A teammate reviews the code. Once they approve, click the **Merge pull request** button on GitHub to merge it into `main`.