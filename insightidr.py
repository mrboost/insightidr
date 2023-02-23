# InsightIDR4Py.py
# Author: Micah Babinski
# Date: 10/1/2021
# Description: Contains useful functions for working with the Rapid7 InsightIDR REST API

# import required modules
import requests, json, time
from datetime import datetime

# define URLs to interact with the API
region = "us" # one of us/eu/ca/au/ap
logs_url = "https://{}.rest.logs.insight.rapid7.com/query/logs/".format(region)
query_url = "https://{}.rest.logs.insight.rapid7.com/query/".format(region)
log_mgmt_url = "https://{}.api.insight.rapid7.com/log_search/management/logs".format(region)

# define API key and headers (remember to store your API keys securely!
api_key = "API_Key_Here"
headers = {"x-api-key": api_key}

def GetLogInfo():
    """Returns metadata about the available log sources."""
    response = requests.get(log_mgmt_url, headers=headers).json()["logs"]
    
    return response


def ListLogSetNames():
    """Returns a list of logset names as they appear in the InsightIDR console."""
    log_info = GetLogInfo()
    logset_names = list(set([log["logsets_info"][0]["name"] for log in log_info]))

    return sorted(logset_names)


def ListLogIdsByLogSetName(logset_name):
    """Returns a list of log ID values for a given logset name."""
    log_info = GetLogInfo()
    log_ids = [log["id"] for log in log_info if log["logsets_info"][0]["name"].upper() == logset_name.upper()]

    return log_ids


def QueryEvents(logset_name, query, time_range="Last 20 Minutes", from_time=None, to_time=None, suppress_msgs=True):
    # convert from/to times as necessary (string to timestamp with milliseconds)
    if not time_range:
        from_time = int(datetime.strptime(from_time, "%m/%d/%Y %H:%M:%S").timestamp()) * 1000
        to_time = int(datetime.strptime(to_time, "%m/%d/%Y %H:%M:%S").timestamp()) * 1000

    # get the relevant Log IDs
    log_ids = ListLogIdsByLogSetName(logset_name)
    # get the time range
    if time_range:
        during = {"time_range": time_range}
    else:
        during = {"from": from_time, "to": to_time}
    body = {"logs": log_ids,
            "leql": {"during": during,
                     "statement": query}}

    # build the first full URL
    url = logs_url + "?per_page=500"

    # retrieve the data
    run = True
    events = []
    cntr = 1
    r = requests.post(url, json=body, headers=headers)
    #print("Gathering events matching: {}.".format(query))
    while run:
        if r.status_code == 202:
            cont = True
            while cont:
                #print("Received 'continue' response, polling again.")
                continue_url = r.json()["links"][0]["href"]
                r = requests.get(continue_url, headers=headers)
                if r.status_code != 202:
                    cont = False
                    break
        elif r.status_code == 200:
            events.extend(r.json()["events"])
            if "links" in r.json():
                #print("Partial response received. Querying for more data.")
                continue_url = r.json()["links"][0]["href"]
                r = requests.get(continue_url, headers=headers)
            else:
                run = False
        else:
            raise ValueError("Query failed without a normal status code. Status code returned was: " + str(r.status_code))
            return
        cntr += 1
        if not suppress_msgs:
            if cntr % 30 == 0:
                print("-Gathered {} events.".format(str(len(events))))

    # filter the event objects to get just the dictionary representation of the event data
    events = [json.loads(event["message"]) for event in events]

    return events


def QueryGroups(logset_name, query, time_range="Last 20 Minutes", from_time=None, to_time=None, suppress_msgs=True):
    # validate input query
    if not "groupby(" in query.lower():
        raise ValueError("Query must contain the groupby() clause!")
    
    # convert from/to times as necessary (string to timestamp with milliseconds)
    if not time_range:
        from_time = int(datetime.strptime(from_time, "%m/%d/%Y %H:%M:%S").timestamp()) * 1000
        to_time = int(datetime.strptime(to_time, "%m/%d/%Y %H:%M:%S").timestamp()) * 1000

    # get the relevant Log IDs
    log_ids = ListLogIdsByLogSetName(logset_name)

    # get the time range
    if time_range:
        during = {"time_range": time_range}
    else:
        during = {"from": from_time, "to": to_time}
    body = {"logs": log_ids,
            "leql": {"during": during,
                     "statement": query}}

    # build the first full URL
    url = logs_url

    # retrieve the data
    run = True
    results = []
    cntr = 1
    r = requests.post(url, json=body, headers=headers)
    #print("Gathering event groups matching query: {}.".format(query))
    while run:
        if r.status_code == 202:
            cont = True
            while cont:
                #print("Received 'continue' response, polling again.")
                continue_url = r.json()["links"][0]["href"]
                r = requests.get(continue_url, headers=headers)
                if r.status_code != 202:
                    cont = False
                    break
        elif r.status_code == 200:
            if "links" in r.json():
                #print("Partial response received. Querying for more data.")
                continue_url = r.json()["links"][0]["href"]
                r = requests.get(continue_url, headers=headers)
            else:
                results.extend(r.json()["statistics"]["groups"])
                run = False
        else:
            raise ValueError("Query failed without a normal status code. Status code returned was: " + str(r.status_code))
            return
        cntr += 1
        if not suppress_msgs:
            if cntr % 30 == 0:
                print("-Gathered {} groups.".format(str(len(results))))

    groups = {}
    for result in results:
        key = list(result.keys())[0]
        value = int(result[key]["count"])
        groups[key] = value

    return groups
