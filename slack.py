from slack_sdk import WebClient
import db

def send_message(message):
    config = db.load_config()
    client = WebClient(token=config['slack_token'])
    response = client.chat_postMessage(text=message,channel="mikran_ogolnie")
    return response

def get_members():
    config = db.load_config()
    slack_token = config['slack_token']
    client = WebClient(token=slack_token)
    result = client.users_list()
    users = []
    for member in result['members']:
        if member['deleted'] == False and member['is_bot'] == False:
            profile = member['profile']            
            users.append((profile['real_name_normalized'],member['id']))

    return users

