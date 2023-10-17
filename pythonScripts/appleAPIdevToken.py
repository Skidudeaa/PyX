
#This code works to create a token for the music api

import jwt
import time
from datetime import datetime, timedelta

# Your MusicKit Key
private_key = '''-----BEGIN PRIVATE KEY-----
MIGTAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBHkwdwIBAQQgwgU9AoPtiY/dd+uy
qOILcu0webOSbYWGJDL0YxBark+gCgYIKoZIzj0DAQehRANCAAR85ngU9imx60tQ
WWhKZ/hQF4eB/oVCagJKs44ZBYYDGfkg+Q9Q+9yBHNTTCoPFcCv4dz1mdRyhogFe
IRHFPTt6
-----END PRIVATE KEY-----'''

# Your Key ID
key_id = '622W2MUUWQ'

# Your Team ID
team_id = 'U4GLQGFNT3'

algorithm = 'ES256'
time_now = int(time.mktime(datetime.now().timetuple()))
time_expires = int(time.mktime((datetime.now() + timedelta(hours=3600)).timetuple()))

headers = {
    'kid': key_id
}

payload = {
    'iss': team_id,
    'iat': time_now,
    'exp': time_expires
}

token = jwt.encode(payload, private_key, algorithm=algorithm, headers=headers)

print(token)
