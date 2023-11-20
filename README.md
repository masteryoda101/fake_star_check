# GitHub Repository Star Analysis Script

## Overview
This Python script analyzes GitHub repositories to identify suspicious stargazing activities. It focuses on detecting repositories that might have artificially inflated their star counts, potentially indicating inauthentic popularity.

## Features
The script performs a detailed analysis of GitHub repositories based on various criteria to flag potentially suspicious activities. The key features include:

1. **Star Time Analysis**: Analyzes the time pattern of stars received by a repository to detect if a significant number of them were given within a short time frame, which might indicate artificial boosting.
2. **User Profile Analysis**: Assesses the profiles of users who starred the repository. 
3. **Repository Star Count**: Evaluates repositories based on their total star count and the pattern of receiving these stars.

## Criteria for Suspicion
The script uses several criteria to determine if a repository's star activity is suspicious:

- A large number of stars received within a short, configurable time window (default is 12 hours).
- A high percentage of stars from users with profiles indicating minimal GitHub activity (e.g., fewer than 2 repositories, fewer than 2 followers).
- Configurable thresholds for the percentage of stars within the time window and the percentage of similar users that flag a repository as suspicious.

## Usage
1. Set the required environment variables, including the GitHub Access Token.
2. Run the script with a list of GitHub repositories to analyze.


## Setup and Execution
1. Install the required Python packages.
2. Set up the `.env` file with your GitHub Access Token.
3. Prepare a text file with a list of repositories to analyze.
4. Run the script: `python <script_name>.py`

