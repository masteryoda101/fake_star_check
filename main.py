import requests
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_repositories(username):
    try:
        url = f"https://api.github.com/users/{username}/repos"
        response = requests.get(url)
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error fetching repositories for {username}. Error: {e}")
        return []


def get_stargazers(owner, repo):
    try:
        url = f"https://api.github.com/repos/{owner}/{repo}/stargazers"
        response = requests.get(url)
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Error fetching stargazers for {owner}. Error: {e}")
        return []


def get_user_details(username):
    try:
        url = f"https://api.github.com/users/{username}"
        response = requests.get(url)
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

    all_stargazers_details = defaultdict(list)

    for repo in repos:
        logging.info(f"Processing repository: {repo['name']}")
        if repo['stargazers_count'] > 40:
            stargazers = get_stargazers(username, repo["name"])

            for user in stargazers:
                user_details = get_user_details(user["login"])
                all_stargazers_details[user_details["created_at"]].append(user_details)

    logging.info("Correlating data...")
    for join_date, details_list in all_stargazers_details.items():
        if len(details_list) > 5:
            similar_users = [details for details in details_list if all(details.values())]

            if similar_users:
                print(f"Join Date: {join_date}")
                print(f"Total Users: {len(details_list)}")
                print(f"Similar Users: {len(similar_users)}")
                print("-----------------------------")


def main():
    username = "stackgpu"
    find_common_join_dates(username)

if __name__ == '__main__':
    main()