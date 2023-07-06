def transform_icon(data):
    if data.get('icon'):
        data['icon'] = f"https://cdn.discordapp.com/icons/{data['id']}/{data['icon']}.png"
    else:
        data['icon'] = "/assets/empty.png"
