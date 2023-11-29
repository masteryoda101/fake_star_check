import requests
from collections import defaultdict, Counter
import os
import dotenv
import datetime
import logging
from visualize_data import visualize_star_pattern

suspicious_logger = logging.getLogger('SuspiciousRepos')
suspicious_logger.setLevel(logging.INFO)
suspicious_handler = logging.FileHandler('SuspiciousReposLog.txt')
suspicious_formatter = logging.Formatter('%(message)s')
suspicious_handler.setFormatter(suspicious_formatter)
suspicious_logger.addHandler(suspicious_handler)

general_logger = logging.getLogger('GeneralLog')
general_logger.setLevel(logging.INFO)
general_handler = logging.FileHandler('Log.txt')
general_formatter = logging.Formatter('%(message)s')
general_handler.setFormatter(general_formatter)
general_logger.addHandler(general_handler)

dotenv.load_dotenv()

GITHUB_ACCESS_TOKEN = os.environ.get('GITHUB_ACCESS_TOKEN')
headers = {'Authorization': f'Bearer {GITHUB_ACCESS_TOKEN}'}

# Variables to change:
SIMILAR_USERS_SUSPICIOUS_PERCENTAGE = 20  # Threshold for similar user percentage
SUSPICIOUS_STAR_PERCENTAGE = 0.6  # 60% threshold
SUSPICIOUS_TIME_WINDOW_HOURS = 24  # Time window to analyze star patterns


def identify_commonly_starred_repositories(similar_users_logins):
    """
     Identify repositories that are commonly starred by a list of users.
    """
    all_starred_repos_of_similar_users = []
    for user_login in similar_users_logins:
        # Fetch repositories starred by each user
        starred_repos_for_user = fetch_repositories_starred_by_user(user_login)
        all_starred_repos_of_similar_users.extend(starred_repos_for_user)

    repo_counts = Counter(all_starred_repos_of_similar_users)

    common_starred_repos = {}
    for repo, count in repo_counts.items():
        if count > 1:
            common_starred_repos[repo] = count
    return common_starred_repos


def fetch_repositories_starred_by_user(username):
    try:
        url = f"https://api.github.com/users/{username}/starred"
        response = requests.get(url, headers=headers)
        repos = response.json()
        # Extract the full name of each repository
        return [repo["full_name"] for repo in repos]
    except Exception as e:
        general_logger.info(f"Error fetching starred repos for {username}. Error: {e}")
        return []


def fetch_repository_details(owner, repo_name):
    try:
        url = f"https://api.github.com/repos/{owner}/{repo_name}"
        response = requests.get(url, headers=headers)
        return response.json()
    except requests.RequestException as e:
        general_logger.info(f"Error fetching details for repository {owner}/{repo_name}. Error: {e}")
        return {}


def get_repositories(username):
    try:
        url = f"https://api.github.com/users/{username}/repos"
        response = requests.get(url, headers=headers)
        return response.json()
    except requests.RequestException as e:
        general_logger.info(f"Error fetching repositories for {username}. Error: {e}")
        return []


def fetch_stargazers_for_repository(owner, repo):
    stargazers = []
    page = 1
    while True:
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/stargazers?page={page}&per_page=100"
            headers['Accept'] = 'application/vnd.github.v3.star+json'
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not data:
                break

            stargazers.extend([(user["user"]["login"], user["starred_at"]) for user in data])

            link_header = response.headers.get('Link', '')
            if 'rel="next"' not in link_header:
                break

            page += 1
        except requests.RequestException as e:
            general_logger.info(f"Error fetching stargazers for {owner}/{repo} on page {page}. Error: {e}")
            break

    return stargazers


def analyze_star_patterns(repo, stargazers):

    if not stargazers:
        return False

    starTimestamps = sorted([datetime.datetime.fromisoformat(star[1].rstrip('Z')) for star in stargazers])

    time_window = datetime.timedelta(hours=SUSPICIOUS_TIME_WINDOW_HOURS)
    max_stars_in_time_window = 0
    total_stars = len(starTimestamps)

    for i in range(total_stars):
        current_time = starTimestamps[i]
        window_end_time = current_time + time_window
        count_in_window = sum(1 for time in starTimestamps if current_time <= time <= window_end_time)
        if count_in_window > max_stars_in_time_window:
            max_stars_in_time_window = count_in_window

    percentage_of_stars_in_window = (max_stars_in_time_window / total_stars) * 100

    suspicious_logger.info(f"Total Stars: {total_stars}")
    suspicious_logger.info(f"Stars within {SUSPICIOUS_TIME_WINDOW_HOURS} hours: {max_stars_in_time_window}")
    suspicious_logger.info(f"Percentage of Total Stars within {SUSPICIOUS_TIME_WINDOW_HOURS} hours: {percentage_of_stars_in_window:.2f}%")
    threshold_percentage = SUSPICIOUS_STAR_PERCENTAGE * 100
    visualize_star_pattern(repo, stargazers)
    if max_stars_in_time_window > total_stars * SUSPICIOUS_STAR_PERCENTAGE:
        return True, threshold_percentage
    else:
        return False, threshold_percentage


def fetch_user_profile_details(username):
    try:
        url = f"https://api.github.com/users/{username}"
        response = requests.get(url, headers=headers)
        user_data = response.json()

        details = {
            "login": user_data["login"],
            "created_at": user_data["created_at"].split("T")[0],
            "has_less_than_2_repos": user_data["public_repos"] < 2,
            "less_than_2_followers": user_data["followers"] < 2,
            "less_than_2_following": user_data["following"] < 2,
            "no_public_gists": user_data["public_gists"] == 0,
            "empty_email": not user_data["email"],
            "not_hireable": not user_data["hireable"],
            "empty_bio": not user_data["bio"],
            "empty_blog": not user_data["blog"],
            "empty_twitter": not user_data["twitter_username"]
        }
        return details
    except requests.RequestException as e:
        general_logger.info(f"Error fetching details for {username}. Error: {e}")
        return []


def check_for_user_similarities(repo, stargazers, total_stargazers):
    total_similar_users = 0
    all_stargazers_details = {}
    similar_users_details = []

    for user_login, starred_at in stargazers:
        user_details = fetch_user_profile_details(user_login)
        all_stargazers_details[user_login] = user_details

    grouped_by_join_date = defaultdict(list)
    for user_login, details in all_stargazers_details.items():
        grouped_by_join_date[details["created_at"]].append(details)

    for join_date, details_list in grouped_by_join_date.items():
        similar_users = [details for details in details_list if all(details.values())]
        total_similar_users += len(similar_users)

        if len(details_list) > 1:
            if similar_users:
                general_logger.info(f"Join Date: {join_date}")
                general_logger.info(f"Total Users: {len(details_list)}")
                general_logger.info(f"Similar Users: {len(similar_users)} \n\n")
    if total_stargazers > 0:
        similar_percentage = (total_similar_users / total_stargazers) * 100
        suspicious_logger.info(f"Percentage of Similar Users: {similar_percentage:.2f}%")

        if similar_percentage > SIMILAR_USERS_SUSPICIOUS_PERCENTAGE:
            suspicious_logger.info(f"⚠️ Repository {repo} failed check 2 of 2 for suspicious star activity, where {similar_percentage:.2f}% of stargazers are similar to each other\n")

            for user_login in stargazers:
                for details in all_stargazers_details.values():
                    if details["login"] == user_login and all(details.values()):
                        similar_users_details.append(details)

            similar_users_logins = [login for login, details in all_stargazers_details.items() if all(details.values())]
            similar_users_count = len(similar_users_details)
            commonly_starred_repos = identify_commonly_starred_repositories(similar_users_logins)
            if commonly_starred_repos:
                general_logger.info("\nCommonly starred repositories among similar users:\n")
                for repo, count in commonly_starred_repos.items():
                    percentage_starred = (count / similar_users_count) * 100
                    general_logger.info(f"{repo} starred by {count} similar users ({percentage_starred:.2f}% of similar users)")
            general_logger.info("-----------------------------")
            general_logger.info("\n")

            print(f"- {repo} - Suspicious Repository (potential fake stars)")
        else:
            suspicious_logger.info(f"✅ Repository {repo} passed check 2 of 2 for suspicious star activity, and does not have an unusual percentage of similar stargazers.\n")
    else:
        suspicious_logger.info(f"✅ Repository {repo} passed check 2 of 2 for suspicious star activity, and does not have an unusual percentage of similar stargazers.\n")


def is_repo_suspicious(repo):
    general_logger.info(f"additional info for repo: {repo}")

    suspicious_logger.info(f"Repo name: {repo}")
    suspicious_logger.info("-----------------------------")

    owner, repo_name = repo.split('/')

    print(f"Processing repository: {repo}")

    repo_details = fetch_repository_details(owner, repo_name)
    stargazers_count = repo_details.get('stargazers_count', 0)

    if stargazers_count > 150:
        stargazers = fetch_stargazers_for_repository(owner, repo_name)
        total_stargazers = len(stargazers)
        suspicious, threshold_percentage = analyze_star_patterns(repo_name, stargazers)
        if suspicious:
            suspicious_logger.info(f"⚠️ Repository {repo} failed check 1 of 2 for suspicious star activity, where over {threshold_percentage}% of stars were given within a 12 hour period!\n")
            suspicious_logger.info(f"checking now for user similarities\n")
            check_for_user_similarities(repo, stargazers, total_stargazers)
        else:
            suspicious_logger.info(f"✅ Repository {repo} passed check for suspicious stars activity, where less than {threshold_percentage}% of stars were given within a 12 hour period!\n")
    if stargazers_count < 1000:
        check_for_user_similarities(repo, stargazers, total_stargazers)

def get_list_of_repos(filename):
    try:
        with open(filename, 'r') as file:
            names = file.readlines()
        names = [name.strip() for name in names]
        print(names)
        return names
    except Exception as e:
        print(f"An error occurred: {e}")
        return []


def main():
    repos_to_check = get_list_of_repos('repo_links_list.txt')
    for repo_name in repos_to_check:
        is_repo_suspicious(repo_name)


if __name__ == '__main__':
    main()
