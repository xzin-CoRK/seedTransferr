import yaml
import requests
import datetime
import sqlite3
import os
import re
import time
import uuid
from contextlib import closing
from datetime import datetime
from datetime import timedelta
from qbittorrent import Client

# Global Variables
hashlist = []   # Establish the list of torrents to clean up
nonce = uuid.uuid4().hex    # Creates a unique id for each script run
TRACKER_REGEX = "https://(fearnopeer\.com|reelflix\.xyz|asiancinema\.me|aither\.cc|beyond-hd\.me|blutopia\.xyz|racing4everyone\.eu|ntelogo\.org|desitorrents\.rocks|skipthetrailers\.xyz|skipthecommericals\.xyz|lst\.gg|thedarkcommunity\.cc|telly\.wtf|upload\.cx|onlyencodes\.cc)/torrents/(\d{1,10})"   # Extracts tracker and torrent id info

class Torrent:
    id = 0
    tracker = ""
    torrent_url = ""
    download_url = ""
    def __init__(self, hash, name, category):
        self.hash = hash
        self.name = name
        self.category = category

def set_wd():
    '''Helper function that sets the working directory to the python script location. Useful when seedTransferr is trigger by cron.'''
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)

def log(message):
    '''print pretty timestamped logs'''
    ts = datetime.now()

    print("%s | %s" % (ts, message))

def setup_db():
    '''make the sqlite database if it doesn't exist yet'''
    with closing(sqlite3.connect('seedTransferr.db', isolation_level=None)) as connection:
        with closing(connection.cursor()) as cursor:
            # Create table if it doesn't exist
            cursor.execute("CREATE TABLE IF NOT EXISTS seedTransferr(hash TEXT, nonce TEXT, name TEXT)")

def read_config():
    '''Parse the config.yaml file to gather trackers, queries, and keys'''
    with open("config.yaml") as stream:
        try:
            config = yaml.safe_load(stream)
            
            # Ensure all needed config values are provided. If not, stop execution
            if 'remote_qbit_url' not in config or not config['remote_qbit_url']:
                msg = "ERROR: Remote Qbittorrent WebUI URL not found in config.yaml"
                log(msg)
                raise Exception(msg)
            
            if 'remote_qbit_user' not in config or not config['remote_qbit_user']:
                msg = "ERROR: Remote Qbittorrent username not found in config.yaml"
                log(msg)
                raise Exception(msg)
            
            if 'remote_qbit_pass' not in config or not config['remote_qbit_pass']:
                msg = "ERROR: Remote Qbittorrent password not found in config.yaml"
                log(msg)
                raise Exception(msg)
            
            if 'local_qbit_url' not in config or not config['local_qbit_url']:
                msg = "ERROR: Local Qbittorrent WebUI URL not found in config.yaml"
                log(msg)
                raise Exception(msg)
            
            # Check for local auth creds when needed
            if config['local_auth_required']:
            
                if 'local_qbit_user' not in config or not config['local_qbit_user']:
                    msg = "ERROR: Local Qbittorrent username not found in config.yaml"
                    log(msg)
                    raise Exception(msg)
                
                if 'local_qbit_pass' not in config or not config['local_qbit_pass']:
                    msg = "ERROR: Local Qbittorrent password not found in config.yaml"
                    log(msg)
                    raise Exception(msg)
            
            global remote_qbit_url, remote_qbit_user, remote_qbit_pass, local_qbit_url
            global local_qbit_user, local_qbit_pass, trackers, inactivity_threshold, local_auth_required
            remote_qbit_url = config['remote_qbit_url']
            remote_qbit_user = config['remote_qbit_user']
            remote_qbit_pass = config['remote_qbit_pass']
            local_qbit_url = config['local_qbit_url']
            local_qbit_user = config['local_qbit_user']
            local_qbit_pass = config['local_qbit_pass']
            local_auth_required = config['local_auth_required']
            
            trackers = config['trackers']
            inactivity_threshold = calculate_inactivity_threshold(config['inactivity_threshold'])
            
        except yaml.YAMLError as exc:
            print(exc)

def qb_connect():
    '''Create a global connection to qb so that we only have to connect once'''
    global remote_qb, local_qb
    remote_qb = Client(remote_qbit_url)
    remote_qb.login(remote_qbit_user, remote_qbit_pass)

    local_qb = Client(local_qbit_url)
    if local_auth_required:
        local_qb.login(local_qbit_user, local_qbit_pass)
    else:
        local_qb.login()

def get_completed_and_paused():
    '''Retrieve all torrents which are done downloading and have reached their ratio limit. These will be marked as "Complete" in qbittorrent'''
    completed_torrents = remote_qb.torrents(filter='completed')

    for torrent in completed_torrents:
        if torrent['state'] == "pausedUP":
            t = Torrent(torrent['hash'], torrent['name'], torrent['category'])
            
            hashlist.append(t)
            log("Migrating %s [completed and paused]" % t.name)

def calculate_inactivity_threshold(threshold_string):
    UNITS = {'s':'seconds', 'm':'minutes', 'h':'hours', 'd':'days', 'w':'weeks'}
    return int(timedelta(**{
        UNITS.get(m.group('unit').lower(), 'seconds'): float(m.group('val'))
        for m in re.finditer(
            r'(?P<val>\d+(\.\d+)?)(?P<unit>[smhdw]?)',
            threshold_string.replace(' ', ''),
            flags=re.I
        )
    }).total_seconds())

def get_inactive():
    '''Retrieve torrents which meet configured inactivity threshold'''
    inactive_torrents = remote_qb.torrents(filter='completed', sort='last_activity')
    unix_ts = (datetime.now() - datetime(1970, 1, 1)).total_seconds()
    for torrent in inactive_torrents:
        age = unix_ts - torrent['last_activity']
        if age >= inactivity_threshold:
            log("Migrating %s [exceeds inactivity threshold]" % torrent['name'])
            t = Torrent(torrent['hash'], torrent['name'], torrent['category'])
            hashlist.append(t)
        else:
            # the results are sorted by last_activity
            # so exit the loop immediately once activity is too fresh rather than looping needlessly through everything
            break

def supplement_id():
    '''Grabs the tracker name and torrent id from the torrent's comment'''
    for torrent in hashlist:
        torrent_details = remote_qb.get_torrent(torrent.hash)
        
        match = re.search(TRACKER_REGEX, torrent_details['comment'])
        torrent.tracker = match.group(1)
        torrent.id = match.group(2)
        torrent.torrent_url = match.group(0).replace('/torrents/', '/api/torrents/')

def get_download_link():
    for torrent in hashlist:
        r = requests.get(torrent.torrent_url, headers={
            'Authorization': 'Bearer ' + [api for api in trackers if api['url'] == torrent.tracker][0]['api_key'],
            'Accept': 'application/json'
        }).json()

        torrent.download_url = r['attributes']['download_link']

def add_to_local_client():
    for torrent in hashlist:
        local_qb.download_from_link(torrent.download_url, category=torrent.category, paused="true")
        log("Adding torrent %s to local client" % torrent.name)
        
        time.sleep(1.5) # Wait a beat for file to show in client

def force_recheck():
    for torrent in hashlist:
        local_qb.recheck(torrent.hash)

def remove_from_seedbox():
    for torrent in hashlist:
        remote_qb.delete_permanently(torrent.hash)
        log("Deleting torrent %s from seedbox" % torrent.name)

def insert_into_db():
    '''Create a database record for each transferred torrent so we can start it next time'''
    with closing(sqlite3.connect('seedTransferr.db', isolation_level=None)) as connection:
        with closing(connection.cursor()) as cursor:
            for torrent in hashlist:
                cursor.execute("INSERT INTO seedTransferr (hash, nonce, name) VALUES('%s', '%s', '%s')" % (torrent.hash, nonce, torrent.name))

def resume_from_db():
    '''Fetch previously transferred torrents and resume them'''
    with closing(sqlite3.connect('seedTransferr.db', isolation_level=None)) as connection:
        with closing(connection.cursor()) as cursor:
            # Get previous hashes and resume
            for to_resume in cursor.execute("SELECT hash, name FROM seedTransferr WHERE nonce <> '%s'" % nonce):
                local_qb.resume(to_resume[0])
                log("Attempting to resume previously added torrent %s" % to_resume[1])
            
            # Delete previous hashes
            cursor.execute("DELETE FROM seedTransferr WHERE nonce <> '%s'" % nonce)


log("seedTransferr started")

# Set the working directory in case seedTransferr was kicked off by cron
set_wd()

# Create the sqlite database if it doesn't exist yet
setup_db()

# Get user config values
read_config()

# Create connection to download clients
qb_connect()

# Get list of completed remote torrents
get_completed_and_paused()

# Get list of torrents which meet the inactivity threshold
get_inactive()

# Get tracker and id
supplement_id()

# Get the .torrent file download link from UNIT3D API to add on local qbit client
get_download_link()

add_to_local_client()

insert_into_db()

force_recheck()

# Removes the torrent from qBittorrent and DELETES THE DATA FROM THE SEEDBOX
remove_from_seedbox()

resume_from_db()

log("seedTransferr completed")