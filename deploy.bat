@echo off
echo Syncing files...
scp -r * woojin@huepi:/home/woojin/music_player

echo Restarting service...
ssh woojin@huepi "sudo systemctl restart music-player.service"

echo Done.