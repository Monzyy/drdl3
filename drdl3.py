#!/usr/bin/env python3

import argparse
import os
import uuid
from datetime import datetime

import requests
import youtube_dl
from crontab import CronTab
from dateutil.parser import parse

PROGRAM_CARD_BASE_URL = 'https://www.dr.dk/mu-online/api/1.4/programcard/'
BUNDLE_BASE_URL = 'https://www.dr.dk/mu/bundle/'


def main(args):
    # Get program card
    url = args.url
    program_card_url = PROGRAM_CARD_BASE_URL + url[url.rfind('/') + 1:]
    request = requests.get(program_card_url)
    program_card = request.json()
    dl_url_list = []
    if program_card.get('PresentationUri'):
        dl_url_list.append(program_card.get('PresentationUri'))

    # Get all from tv-series or season
    if args.tvseries or args.season:
        series_urn = program_card.get('SeriesUrn')
        series_url = 'https://www.dr.dk/mu-online/api/1.4/list/view/seasons?id=' + series_urn + '&limit=0'
        request = requests.get(series_url)
        series_data = request.json()
        dl_url_list = []
        for season in series_data.get('Items'):
            if args.tvseries or (args.season and season['SeasonNumber'] == program_card['SeasonNumber']):
                for episode in season.get('Episodes').get('Items'):
                    dl_url_list.append(episode.get('PresentationUri'))

    # upcoming
    if args.crontab:
        bundle_url = BUNDLE_BASE_URL + program_card.get('SeriesUrn')
        request = requests.get(bundle_url)
        bundle_data = request.json()
        bundle_data = bundle_data.get('Data')[0]
        members = bundle_data.get('Relations')
        members = [mem['Slug'] for mem in members if mem['Kind'] == 'Member' and 'BundleType' not in mem]

        upcoming_release_dates = []
        for member in members:
            request = requests.get(PROGRAM_CARD_BASE_URL + member)
            data = request.json()
            date = parse(data.get('SortDateTime')).replace(tzinfo=None)
            if data.get('PresentationUri') is None and date > datetime.now():
                upcoming_release_dates.append(parse(data.get('SortDateTime')))

        cron = CronTab(user=True)

        if args.jobid:
            cron.remove_all(comment=f'drdl3: {args.jobid}')
        # If there are upcoming episodes create a new crontab
        if min(upcoming_release_dates).replace(tzinfo=None) > datetime.now():
            cron_id = str(uuid.uuid4())
            job_args = args.url
            job_args += f' -o {args.outputdir}' if args.outputdir else ''
            job_args += f' -t' if args.tvseries else ''
            job_args += f' -s' if args.season else ''
            job_args += ' -c'
            job_args += f' -j {cron_id}'
            job = cron.new(command=' '.join([os.path.abspath(__file__), job_args]), comment=f'drdl3: {cron_id}')
            job.setall(min(upcoming_release_dates))
            cron.write()

    ydl_opts = {
        'write_all_thumbnails': True,
        'writesubtitles': True,
        'download_archive': 'youtube-dl-archive.txt'
    }
    if args.outputdir:
        os.chdir(args.outputdir)
    if not dl_url_list:
        print('[drdl3] no episodes available')
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download(dl_url_list)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('url', help='Url to video from dr.dk/tv')
    parser.add_argument('-o', '--outputdir', help='Specify output directory')
    parser.add_argument('-t', '--tvseries', action='store_true', help='Download all available in tv series')
    parser.add_argument('-s', '--season', action='store_true', help='Download all available in the season')
    parser.add_argument('-c', '--crontab', action='store_true',
                        help='Setup a crontab for downloading the next episode when it releases')
    parser.add_argument('-j', '--jobid', help='Cronjob id. Used for deleting old cronjobs')
    args = parser.parse_args()
    main(args)
