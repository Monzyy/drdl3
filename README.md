# drdl3
DR Downloader 3

Installation:
```
sudo apt install ffmpeg
cd drdl3
pip install -r requirements.txt
```

Commands:
```
usage: drdl3.py [-h] {dl,lsubs,add,rsubs,upcoming} ...

positional arguments:
  {dl,lsubs,add,rsubs,upcoming}
                        Sub-command help
    dl                  Download episodes
    lsubs               List subscriptions
    add                 Add new subscription
    rsubs               Remove subscriptions
    upcoming            List upcoming episodes
```
Downloading:
```
usage: drdl3.py dl [-h] [-o OUTPUTDIR] [-t] [-s] [--subscribe] url

positional arguments:
  url                   Url to video from dr.dk/tv

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUTDIR, --outputdir OUTPUTDIR
                        Specify output directory
  -t, --tvseries        Download all available in tv series
  -s, --season          Download all available in the season
  --subscribe           Subscribe to the episode, season or series.
```
Subscribe:
```
usage: drdl3.py add [-h] [-o OUTPUTDIR] [-t] [-s] [-r [RATE]] url

positional arguments:
  url                   Url to video from dr.dk/tv

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUTDIR, --outputdir OUTPUTDIR
                        Specify output directory
  -t, --tvseries        Subscribe to the tv series
  -s, --season          Subscribe to the season
  -r [RATE], --rate [RATE]
                        Set update rate to every x hours
```
Remove subscription:
```
usage: drdl3.py rsubs [-h] int [int ...]

positional arguments:
  int         Index of subscription

optional arguments:
  -h, --help  show this help message and exit
```

