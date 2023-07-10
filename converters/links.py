def transform_icon(data):
    data['textIcon'] = ''.join([x[:1] for x in data.get('name').split(' ')[:2]])
    if data.get('icon'):
        data['icon'] = f"https://cdn.discordapp.com/icons/{data['id']}/{data['icon']}.png"
    else:
        data['icon'] = ""
