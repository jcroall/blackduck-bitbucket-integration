#!/usr/bin/python3

import argparse
import os
import sys
import json
import requests
import subprocess

python3_path = "/usr/bin/python3"

parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Tool for launching Black Duck scan from BitBucket Data Center and Jenkins Pipeline')
parser.add_argument('--debug', default=0, help='set debug level [0-9]')
parser.add_argument('--bb-url', required=True, help='BitBucket URL')
parser.add_argument('--blackduck-url', required=True, help='BlackDuck URL')

args = parser.parse_args()

debug = int(args.debug)
bb_url = args.bb_url
blackduck_url = args.blackduck_url

bb_username = os.getenv("BITBUCKET_USERNAME")
bb_password = os.getenv("BITBUCKET_PASSWORD")
blackduck_token = os.getenv("BLACKDUCK_TOKEN")
pull_number = os.getenv("CHANGE_ID")

project = os.getenv("BITBUCKET_PROJECT")
repo_slug = os.getenv("BITBUCKET_REPO")

change_target = os.getenv("CHANGE_TARGET")

print(f"Diagnostics:")
for k, v in os.environ.items():
    print(f'{k}={v}')

if pull_number:
  print(f"Run RAPID scan")
  command = f"{python3_path} -u -m bdscan.bdscanaction --bd_url {blackduck_url} --bd_token {blackduck_token} --mode RAPID --debug {debug} --scm bitbucket-dc --comment_on_pr true --code-insights insights.json --debug {debug}"
  print(f"EXEC: {command}")
  completedProc = subprocess.run(command.split())
else:
  print(f"Run INTELLIGENT scan")
  command = f"{python3_path} -u -m bdscan.bdscanaction --bd_url {blackduck_url} --bd_token {blackduck_token} --mode INTELLIGENT --debug {debug} --scm bitbucket-dc --debug {debug}"
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

sys.exit(0)
