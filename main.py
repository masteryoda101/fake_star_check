import requests
from collections import defaultdict, Counter
import os
import dotenv
import redis
from bifrost import common, package_utils
from bifrost import library_utils, url_utils, git_utils
import datetime
from threading import Thread
import time
import logging
import queue
from prometheus_client import  Gauge, Counter

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

#logging.basicConfig(filename='SuspiciousReposLog.txt', level=logging.INFO, format='%(message)s')
#common.init_logging('log.txt', file_level=logging.DEBUG, stdout_level=logging.INFO)

REDIS_HOST = common.read_environment_variable('REDIS_HOST', default='localhost')
redis_session = redis.Redis(host=REDIS_HOST, encoding="utf-8", decode_responses=True, socket_connect_timeout=1)

LIBRARY_TOKEN = common.read_environment_variable('LIBRARY_TOKEN')
library_client = library_utils.LibraryClient(LIBRARY_TOKEN)
GITHUB_ACCESS_TOKEN = os.environ.get('GITHUB_ACCESS_TOKEN')
headers = {'Authorization': f'Bearer {GITHUB_ACCESS_TOKEN}'}

PACKAGE_GAUGE_COUNTER = Gauge('packages_pending_scanning', 'Counter of packages that are pending to be scanned')
THREADS_COUNTER = Counter('static_threads_count', 'Counts number of analysis worker threads')
packages_queue = queue.Queue()
running = True

SUPPORTED_VCS_HOSTNAMES = 'github.com'

SUSPICIOUS_THRESHOLD = 15  # in percentages.


def identify_commonly_starred_repositories(similar_users_logins):
    all_starred_repos_of_similar_users = []
    for user_login in similar_users_logins:
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
        return [repo["full_name"] for repo in response.json()]
    except requests.RequestException as e:
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
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            if not data:
                break

            stargazers.extend(data)

            link_header = response.headers.get('Link', '')
            if 'rel="next"' not in link_header:
                break

            page += 1
        except requests.RequestException as e:
            general_logger.info(f"Error fetching stargazers for {owner}/{repo} on page {page}. Error: {e}")
            break

    return stargazers


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


def is_repo_suspicious(repo):
        owner, repo_name = repo.split('/')

        if redis_session.exists(f'dustico:repocheck:gitrepos:{repo}'):
            return

        redis_session.set(f'dustico:repocheck:gitrepos:{repo}', '', ex=common.ONE_DAY_SECONDS * 30)

        print(f"Processing repository: {repo}")

        repo_details = fetch_repository_details(owner, repo_name)
        stargazers_count = repo_details.get('stargazers_count', 0)

        all_stargazers_details = {}
        total_stargazers = 0
        total_similar_users = 0

        if stargazers_count > 40:
            stargazers = fetch_stargazers_for_repository(owner, repo_name)
            total_stargazers = len(stargazers)

            for user in stargazers:
                user_login = user["login"]
                user_details = fetch_user_profile_details(user_login)
                all_stargazers_details[user_login] = user_details

            suspicious_logger.info(f"Repo name: {repo}")
            suspicious_logger.info("-----------------------------")

            grouped_by_join_date = defaultdict(list)
            for user_login, details in all_stargazers_details.items():
                grouped_by_join_date[details["created_at"]].append(details)

            for join_date, details_list in grouped_by_join_date.items():
                similar_users = [details for details in details_list if all(details.values())]
                total_similar_users += len(similar_users)

                if len(details_list) > 5:
                    if similar_users:
                        suspicious_logger.info(f"Join Date: {join_date}")
                        suspicious_logger.info(f"Total Users: {len(details_list)}")
                        suspicious_logger.info(f"Similar Users: {len(similar_users)} \n\n")
            if total_stargazers > 0:
                similar_percentage = (total_similar_users / total_stargazers) * 100
                suspicious_logger.info(f"Percentage of Similar Users: {similar_percentage:.2f}%")

                if similar_percentage > SUSPICIOUS_THRESHOLD:
                    suspicious_logger.info(f"⚠️ Repository {repo} is over threshold of similar stargazers!\n")

                    similar_users_details = []
                    for user in stargazers:
                        for details in all_stargazers_details.values():
                            if details["login"] == user["login"] and all(details.values()):
                                similar_users_details.append(details)

                    similar_users_logins = [login for login, details in all_stargazers_details.items() if all(details.values())]
                    similar_users_count = len(similar_users_details)
                    commonly_starred_repos = identify_commonly_starred_repositories(similar_users_logins)
                    if commonly_starred_repos:
                        suspicious_logger.info("\nCommonly starred repositories among similar users:\n")
                        for repo, count in commonly_starred_repos.items():
                            percentage_starred = (count / similar_users_count) * 100
                            suspicious_logger.info(f"{repo} starred by {count} similar users ({percentage_starred:.2f}% of similar users)")
                    suspicious_logger.info("-----------------------------")
                    suspicious_logger.info("\n")

                    print(f"- {repo} - Suspicious Repository (potential fake stars)")
                else:
                    print(f"{repo}: Not found to be suspicious of fake stars.")
            else:
                print(f"{repo}: Not found to be suspicious of fake stars.")


def process_new_pypi_packages():
    while running:
        try:
            from_timestamp = int(datetime.datetime.now().timestamp() * 1000)
            for package in library_client.stream_new_packages(package_types=['pypi'], polling_interval_seconds=60, page_size=1000, from_timestamp=from_timestamp):
                print(package['name'])
                package_name = package['name']
                package_type = package['type']
                package_id = f'{package_type}-{package_name}'.lower()

                if redis_session.exists(f'dustico:repocheck:packages:{package_id}'):
                    continue

                redis_session.set(f'dustico:repocheck:packages:{package_id}', '', ex=common.ONE_DAY_SECONDS * 30)

                packages_queue.put(package)
        except:
            general_logger.info('error handling new pypi package releases')

        finally:
            time.sleep(30)


def pypi_get_package_git_url(package_json):
    project_urls = package_json.get('info', {}).get('project_urls', {})
    if not project_urls:
        return

    for key in ['Source', 'Source Code', 'Homepage', 'Download']:
        url = project_urls.get(key)
        if not url:
            continue

        hostname = url_utils.get_hostname(url)
        if hostname not in SUPPORTED_VCS_HOSTNAMES:
            continue

        url = git_utils.normalize_git_repository_url(url, raise_on_failure=False)
        if not url:
            continue

        return url


def packages_queue_worker():
    while running:
        try:
            package = packages_queue.get()
            package_name = package['name']
            package_version = package['version']
            package_data = package_utils.pypi_get_package_raw_data(package_name, package_version)
            package_repo_link = pypi_get_package_git_url(package_data)
            if package_repo_link != None:
                repo = package_repo_link.split("github.com/")[1]
                print(f'\n{package_name} - repo: {package_repo_link}')
                is_repo_suspicious(repo)
        except Exception as e:
            general_logger.info(f'unexpected error handling packages queue \n {e}')
        finally:
            PACKAGE_GAUGE_COUNTER.dec()
            packages_queue.task_done()


def main():

    Thread(target=process_new_pypi_packages, daemon=True).start()

    worker_threads = 10
    for _ in range(worker_threads):
        Thread(target=packages_queue_worker, daemon=True).start()

    while True:
        time.sleep(1)

    """ For testing purposes"""
    #repo = "stackgpu/Simple-GPU"
    #is_repo_suspicious(repo)

if __name__ == '__main__':
    main()