import requests
from collections import defaultdict
import logging
import dotenv
import os


dotenv.load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

GITHUB_ACCESS_TOKEN = os.environ.get('GITHUB_ACCESS_TOKEN')
headers = {'Authorization': f'Bearer {GITHUB_ACCESS_TOKEN}'}
SUSPICIOUS_THRESHOLD = 10  # threshold of 10%

def get_repositories(username):
    try:
        url = f"https://api.github.com/users/{username}/repos"
        response = requests.get(url, headers=headers)
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error fetching repositories for {username}. Error: {e}")
        return []


def get_stargazers(owner, repo):
    stargazers = []
    page = 1

    while True:
        try:
            url = f"https://api.github.com/repos/{owner}/{repo}/stargazers?page={page}&per_page=100"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if not data:
                break

            stargazers.extend(data)

            link_header = response.headers.get('Link', '')
            if 'rel="next"' not in link_header:  # Check if there's a next page
                break

            page += 1
        except requests.RequestException as e:
            logging.error(f"Error fetching stargazers for {owner}/{repo} on page {page}. Error: {e}")
            break

    return stargazers


def get_user_details(username):
    try:
        url = f"https://api.github.com/users/{username}"
        response = requests.get(url, headers=headers)
        user_data = response.json()

        details = {
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
        logging.error(f"Error fetching details for {username}. Error: {e}")
        return []


def find_common_join_dates(username):
    logging.info("Fetching repositories...")
    repos = get_repositories(username)

    suspicious_repos = []

    for repo in repos:
        logging.info(f"Processing repository: {repo['name']}")

        all_stargazers_details = defaultdict(list)
        total_stargazers = 0
        total_similar_users = 0

        if repo['stargazers_count'] > 40:
            stargazers = get_stargazers(username, repo["name"])
            total_stargazers = len(stargazers)

            for user in stargazers:
                user_details = get_user_details(user["login"])
                all_stargazers_details[user_details["created_at"]].append(user_details)

        print(f"Repo name: {repo['name']}")
        print("-----------------------------")

        for join_date, details_list in all_stargazers_details.items():
            similar_users = [details for details in details_list if all(details.values())]
            total_similar_users += len(similar_users)

            if len(details_list) > 5:
                if similar_users:
                    print(f"Join Date: {join_date}")
                    print(f"Total Users: {len(details_list)}")
                    print(f"Similar Users: {len(similar_users)}")
                    print("-----------------------------")


        if total_stargazers > 0:
            similar_percentage = (total_similar_users / total_stargazers) * 100
            print(f"Percentage of Similar Users: {similar_percentage:.2f}%")

            if similar_percentage > SUSPICIOUS_THRESHOLD:
                print(f"⚠️ Repository {repo['name']} is suspicious of fake stars!")
                suspicious_repos.append(repo['name'])

        print("\n")

    if suspicious_repos:
        print("Suspicious Repositories (potential fake stars):")
        for repo_name in suspicious_repos:
            print(f"- {repo_name}")
    else:
        print("No repositories found to be suspicious of fake stars.")


def main():
    username = "stackgpu"
    find_common_join_dates(username)

if __name__ == '__main__':
    main()