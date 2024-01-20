# seedTransferr

This script automates the transfer of qBittorrent torrents from your remote seedbox to another/local permaseed box. It will:
1) Remove torrent from seedbox qBittorrent (deleting associated data) based on user-configured rules
2) Add torrent to local qBittorrent, preserving the original category
3) Force recheck on local qBittorrent

## Limitations

1. This does not transfer the actual torrent content, and assumes that the torrent content already exists within your local qBittorrent's download folder (and associated category folder) for proper functionality. There are many ways to achieve this: I've had good success with a cronjob running rclone at 30 minute intervals.
2. Because rechecking the torrent after adding it to your local qBittorrent client can take a long time (with variability based on your CPU and torrent file size), this script will not start seeding. You will be able to see the torrents in the "Complete" status after the recheck completes, and will need to manually click resume at some point.

## Which torrents are removed?

seedTransferr will automatically remove anything that is Completed and Paused. So if you configure a max ratio and set qBit to pause when that ratio is hit, seedTransferr will pick up those torrents for transfer to permaseed.

You can also configure an "inactivity threshold". If a torrent has been inactive for more than your threshold, seedTransferr will pick it up for transfer to permaseed. For example, if you set inactivity threshold to "6d", any torrent inactive for 6 days or more will be migrated. If you set the threshold for "1d 1h", and torrent inactive for more than 25 hours will be transferred to permaseed.

## How to run automatically?
Use cron.
```bash
crontab -e
```
Then tell cron to run every night at midnight and log the results in the cron.log file:
```bash
0 0 * * * python ~/seedTransferr/seedTransferr.py >> ~/seedTransferr/cron.log 2>&1
```

## Supported Trackers

This script currently only supports FnP and RFX. This is based on the UNIT3D API, so in theory any UNIT3D tracker will work. However, I'm not a member of any other UNIT3D trackers, so I haven't been able to test and implement those. If you have a tracker you'd like added, let's talk.