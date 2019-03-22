# drdl3
DR Downloader 3

```
usage: drdl3.py [-h] [-o OUTPUTDIR] [-t] [-s] [-c] [-j JOBID] url

positional arguments:
  url                   Url to video from dr.dk/tv

optional arguments:
  -h, --help            show this help message and exit
  -o OUTPUTDIR, --outputdir OUTPUTDIR
                        Specify output directory
  -t, --tvseries        Download all available in tv series
  -s, --season          Download all available in the season
  -c, --crontab         Setup a crontab for downloading the next episode when
                        it releases
  -j JOBID, --jobid JOBID
                        Cronjob id. Used for deleting old cronjobs
```
