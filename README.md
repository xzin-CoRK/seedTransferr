# seedTransferr

seedTransferr is for people who use a seedbox for initial downloading/sharing before moving their torrents to another device for long-term seeding. This script automates the cleanup and transfer of qBittorrent torrents from your remote seedbox to your permaseed box. It will:
1) Remove torrent from seedbox qBittorrent (**⚠️deleting associated data⚠️**) based on user-configured rules
2) Add torrent to local qBittorrent, preserving the original category
3) Force recheck and start seeding on local qBittorrent

## Installation

```
git clone https://github.com/xzin-CoRK/seedTransferr.git
cd seedTransferr
pip install -r requirements.txt
mv config.yaml.example config.yaml
```

## Configuration

After installing, you need to edit the config.yaml file to input information about your seedbox qBit client, your local qBit client, and your tracker API keys (which are used to download the .torrent files on your local client).

## Running the script
```
python3 seedTransferr.py
```

## Limitations

1. Only works with qBittorrent right now.
2. This does not transfer the actual torrent content, and assumes that the torrent content already exists within your local qBittorrent's download folder (and associated category folder) for proper functionality. There are many ways to achieve this: I've had good success with a cronjob running rclone at 30 minute intervals.
3. Because rechecking the torrent after adding it to your local qBittorrent client can take a long time (with variability based on your CPU, block size, and torrent file size), this script will not start seeding right away. Instead, it will keep track of which torrents were transferred and attempt to start seeding them on the subsequent run. If you use the cron configuration below, the script will run at midnight and 3am. This gives a 3-hour block for torrents transferred during the midnight run to finish checking before the 3am run triggers them to begin seeding, thereby minimizing seeding downtime. (Of course, if any torrent crosses the threshold between midnight and 3am, it won't be resumed until the next midnight run. You could avoid this downtime by running the script at a faster interval, like every hour: there's really no harm in running it too often.)

## Warning / Liability

As mentioned above, this script assumes that your torrent data has already been moved from your remote seedbox to your local seedbox. It will delete the data from affected torrents from your remote seedbox to free up space. This data cannot be recovered, and you assume all liability for any data that is unintentionally lost/deleted.

## Which torrents are removed?

### Torrents at/above ratio limit
seedTransferr will automatically remove anything that is Completed and Paused. So if you configure a max ratio and set qBit to pause when that ratio is hit, seedTransferr will pick up those torrents for transfer to permaseed.

### Inactive torrents
You can also configure an "inactivity threshold". If a torrent has been inactive for more than your threshold, seedTransferr will pick it up for transfer to permaseed. For example, if you set inactivity threshold to "6d", any torrent inactive for 6 days or more will be migrated. If you set the threshold for "1d1h", any torrent inactive for more than 25 hours will be transferred to permaseed.

## How to run automatically?
Use cron.
```bash
$ crontab -e
```
Then tell cron to run every night at midnight and 3am, logging the results in the cron.log file:
```bash
0 0,3 * * * python3 ~/seedTransferr/seedTransferr.py >> ~/seedTransferr/cron.log 2>&1
```

## Supported Trackers

seedTransferr currently only supports FnP and RFX. It utilizes the UNIT3D API, so in theory any UNIT3D tracker will work. However, I'm not a member of any other UNIT3D trackers, so I haven't been able to test and implement those. If you have a tracker you'd like added, let's talk.