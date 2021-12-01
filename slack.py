from slack_sdk.webhook import WebhookClient
from slack_sdk import WebClient

slack_token = "xoxb-38857451107-2800518310881-AWV9fZFkYifgHKySdOcgH8bi"
client = WebClient(token=slack_token)
url = 'https://hooks.slack.com/services/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'
webhook = WebhookClient(url)

def send_message(message):
    response = webhook.send(text=message)
    return response

def get_members():
    result = client.users_list()
    users = []
    for member in result['members']:
        if member['deleted'] == False:
            profile = member['profile']
            #print(profile['real_name_normalized'],': ',profile['display_name_normalized'])
            users.append(profile['real_name_normalized'])

    return users

