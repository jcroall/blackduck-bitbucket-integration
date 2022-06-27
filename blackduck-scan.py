#!/usr/bin/python3

import argparse
import os
import sys
import json
import requests
import subprocess

#python3_path = "/Users/jcroall/git/github/blackduck-direct-scan-action/venv/bin/python3"
python3_path = "/usr/bin/python3"

parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Tool for launching Black Duck scan from BitBucket Data Center and Jenkins Pipeline')
parser.add_argument('--debug', default=0, help='set debug level [0-9]')

parser.add_argument('--bb-url', required=True, help='BitBucket URL')

parser.add_argument('--blackduck-url', required=True, help='BlackDuck URL')
parser.add_argument('--blackduck-token', required=True, help='BlackDuck token')

parser.add_argument('--get-branch', default=False, action='store_true', help='Get branch from input and exit')
parser.add_argument('--get-clone-href', default=False, action='store_true', help='Get clone href from input and exit')

#parser.add_argument('--comment-on-github-pr', default=False, action='store_true', help='Comment on       GitHub PR')

args = parser.parse_args()

debug = int(args.debug)
get_branch = args.get_branch
get_clone_href = args.get_clone_href
bb_url = args.bb_url

blackduck_url = args.blackduck_url
blackduck_token = args.blackduck_token

bb_username = os.getenv("BITBUCKET_USERNAME")
bb_password = os.getenv("BITBUCKET_PASSWORD")

if not bb_username or not bb_password:
    print(f"ERROR: Must specify BITBUCKET_USER and BITBUCKET_PASSWORD")
    sys.exit(1)

# Parse WebHook payload
jsonpath_string = os.getenv("JSONPATH")
jsonpath = json.loads(jsonpath_string)

if (debug): print("JSONPATH: " + json.dumps(jsonpath, indent=4) + "\n")

repo = None
repo_slug = None
ref = None
branch = None
from_href = None
project = None
pull_number = None

# Is the webhook for a push or pull request?
if jsonpath['eventKey'] == "repo:refs_changed":
    if debug: print(f"event=repo:refs_changed")

    project = jsonpath['repository']['project']['key']
    repo = jsonpath['repository']['name']
    repo_slug = jsonpath['repository']['slug']

    ref = None
    changes = jsonpath['changes']
    branch = None
    for change in changes:
        if 'ref' in change and 'type' in change['ref'] and change['ref']['type'] == "BRANCH":
            branch = change['ref']['displayId']
            ref = change['toHash'] # JC: Is it fromHash or toHash?

    if debug:
        print(f"DEBUG: project={project} repo={repo}")
        print(f"DEBUG: branch={branch}")

    # The commit may be for a PR, check and see
    headers = {'content-type': 'application/json'}

    bb_url2 = f"{bb_url}/rest/api/1.0/projects/{project}/repos/{repo}/pull-requests?limit=500" # Note limit

    isLastPage = False
    nextPageStart = 0
    pulls = []
    while isLastPage == False:
        if debug: print(f"DEBUG: url={bb_url2} headers={headers}")
        r = requests.get(bb_url2 + f"&start={nextPageStart}", verify=False, auth=(bb_username, bb_password), headers=headers)

        if (r.status_code > 250):
            print(f"ERROR: Unable to get BitBucket pull request activities ({r.status_code}):")
            print(r.json())
            sys.exit(1)

        if debug: print(f"DEBUG: Got PR Comments: {r.json()}")

        for pull in r.json()['values']:
            pulls.append(pull)

        if 'nextPageStart' in r.json():
            nextPageStart = r.json()['nextPageStart']
        if 'isLastPage' in r.json() and r.json()['isLastPage'] == True:
            isLastPage = True

    if debug: print(f"DEBUG: Got all pull requests={pulls}")

    from_href = None
    pull_number = None
    found_branch = False
    for pull in pulls:
        if pull['fromRef']['displayId'] == branch:
            if debug: print(f"DEBUG: Found from branch={branch}")

            pull_number = pull['id']

            for link in pull['fromRef']['repository']['links']['clone']:
                if debug: print(f"DEBUG: link name={link['name']} ref={link['href']}")
                if link['name'] == "ssh":
                    from_href = link['href']

            found_branch = True

            break

    if (branch == None and from_href == None):
        print(f"ERROR: Unable to parse JSONPATH={jsonpath}")
        sys.exit(1)

    if (found_branch == False):
        if debug: print(f"DEBUG: Could not find a PR for this branch, using built-in")

        from_href = None
        for link in jsonpath['repository']['links']['clone']:
            if debug: print(f"DEBUG: link name={link['name']} ref={link['href']}")
            if link['name'] == "ssh":
                from_href = link['href']

    if debug:
        print(f"INFO: from_href={from_href}")
        print(f"INFO: branch={branch}")
        if pull_number: print(f"INFO: pull_number={pull_number}")

elif jsonpath['eventKey'] == "pr:opened":
    if debug: print(f"event=pr:opened")

    pull = jsonpath['pullRequest']
    pull_number = pull['id']

    from_href = None
    for link in pull['fromRef']['repository']['links']['clone']:
        if debug: print(f"DEBUG: link name={link['name']} ref={link['href']}")
        if link['name'] == "ssh":
            from_href = link['href']

    project = pull['fromRef']['repository']['project']['key']
    branch = pull['fromRef']['displayId']
    ref = pull['fromRef']['latestCommit']
    repo_slug = pull['fromRef']['repository']['slug']

    if debug:
        print(f"INFO: from_href={from_href}")
        print(f"INFO: branch={branch}")
        print(f"INFO: pull_number={pull_number}")

else:
    if jsonpath: print(f"Event '{jsonpath['eventKey']} not recognized")
    sys.exit(1)


if (get_branch):
    print(f"{branch}")
    sys.exit(0)

if (get_clone_href):
    print(f"{from_href}")
    sys.exit(0)

if ("snps-fix-pr" in branch):
    print("Do not process a SNPS fix pr")
    sys.exit(0)

if jsonpath['eventKey'] == "repo:refs_changed":
    print(f"Run BD Scan on push")

    os.environ['BITBUCKET_URL'] = bb_url
    os.environ['BITBUCKET_USERNAME'] = bb_username
    os.environ['BITBUCKET_PASSWORD'] = bb_password

    os.environ['BITBUCKET_URL'] = bb_url
    os.environ['BITBUCKET_PROJECT'] = project
    os.environ['BITBUCKET_REPO'] = repo_slug
    os.environ['BITBUCKET_REF'] = ref
    os.environ['BITBUCKET_BRANCH'] = branch
    os.environ['BITBUCKET_PULL_NUMBER'] = "0" # pull_number
    os.environ['BITBUCKET_PROJECT'] = project

    if debug:
        print(f"DEBUG: project = {project}")
        print(f"DEBUG: repo = {repo_slug}")
        print(f"DEBUG: ref = {ref}")
        print(f"DEBUG: branch = {branch}")
        print(f"DEBUG: pull_number = 0")
        print(f"DEBUG: project = {project}")

    print(f"Run FULL scan")
    command = f"{python3_path} -u -m bdscan.bdscanaction --bd_url {blackduck_url} --bd_token {blackduck_token} --mode INTELLIGENT --debug {debug} --fix_pr true --upgrade_major false --scm bitbucket-dc"
    print(f"EXEC: {command}")
    completedProc = subprocess.run(command.split())

    print(f"Run RAPID scan and generate fix pr")
    command = f"{python3_path} -u -m bdscan.bdscanaction --bd_url {blackduck_url} --bd_token {blackduck_token} --mode RAPID --fix_pr true --debug {debug} --fix_pr true --upgrade_major false --scm bitbucket-dc"
    print(f"EXEC: {command}")
    completedProc = subprocess.run(command.split())

elif jsonpath['eventKey'] == "pr:opened":
    print(f"Run BD Scan on pr")

    os.environ['BITBUCKET_URL'] = bb_url
    os.environ['BITBUCKET_USERNAME'] = bb_username
    os.environ['BITBUCKET_PASSWORD'] = bb_password

    os.environ['BITBUCKET_PROJECT'] = project
    os.environ['BITBUCKET_REPO'] = repo_slug
    os.environ['BITBUCKET_REF'] = ref
    os.environ['BITBUCKET_BRANCH'] = branch
    os.environ['BITBUCKET_PULL_NUMBER'] = str(pull_number)
    os.environ['BITBUCKET_PROJECT'] = project

    if debug:
        print(f"DEBUG: project = {project}")
        print(f"DEBUG: repo = {repo_slug}")
        print(f"DEBUG: ref = {ref}")
        print(f"DEBUG: branch = {branch}")
        print(f"DEBUG: pull_number = {pull_number}")
        print(f"DEBUG: project = {project}")

    command = f"{python3_path} -u -m bdscan.bdscanaction --bd_url {blackduck_url} --bd_token {blackduck_token} --mode RAPID --comment_on_pr true --upgrade_major false --code-insights code-insights.json --debug {debug} --scm bitbucket-dc"

    print(f"EXEC: {command}")
    completedProc = subprocess.run(command.split())

    if completedProc.returncode > 0:
        headers = {'content-type': 'application/json'}
        error_comment = {
            'text': "Error executing Black Duck BitBucket integration, please see logs"
        }
        bb_url = f"{bb_url}/rest/api/1.0/projects/{project}/repos/{repo_slug}/pull-requests/{pull_number}/comments"
        r = requests.post(bb_url, verify=False, auth=(bb_username, bb_password), headers=headers, json=error_comment)

        if (r.status_code > 250):
            print(f"ERROR: Unable to log error as comment: ({r.status_code}):")
            print(r.json())
            sys.exit(1)

else:
    print(f"Event '{data['eventKey']} not recognized")
    sys.exit(1)
