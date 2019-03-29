#!/usr/bin/env python3

import argparse
import os
import re
from datetime import datetime

import requests
import youtube_dl
from crontab import CronTab
from dateutil.parser import parse

PROGRAM_CARD_BASE_URL = 'https://www.dr.dk/mu-online/api/1.4/programcard/'
BUNDLE_BASE_URL = 'https://www.dr.dk/mu/bundle/'


def download(args):
    # Get program card
    url = args.url
    program_card = program_card_from_url(url)
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

    ydl_opts = {
        'write_all_thumbnails': True,
        'writesubtitles': True
    }
    if args.outputdir:
        os.chdir(args.outputdir)
    if not dl_url_list:
        print('[drdl3] no episodes available')
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download(dl_url_list)

    if args.subscribe:
        add_subscription(args)


def upcoming(args):
    program_card = program_card_from_url(args.url)
    bundle_url = BUNDLE_BASE_URL + program_card.get('SeriesUrn')
    request = requests.get(bundle_url)
    bundle_data = request.json()
    bundle_data = bundle_data.get('Data')[0]
    members = bundle_data.get('Relations')
    members = [mem['Slug'] for mem in members if mem['Kind'] == 'Member' and 'BundleType' not in mem]

    for member in members:
        request = requests.get(PROGRAM_CARD_BASE_URL + member)
        data = request.json()
        date = parse(data.get('SortDateTime')).replace(tzinfo=None)
        if data.get('PresentationUri') is None and date > datetime.now():
            print('[drdl3]', data.get('SortDateTime'), data.get('Title'))


def list_subscriptions(args):
    cron = CronTab(user=True)
    subscriptions = cron.find_command('drdl3.py')
    for index, sub in enumerate(subscriptions):
        m = re.search(r'[^.\s]*https?://(?:www\.)?dr\.dk/(?:tv/se|nyheder|radio/ondemand)/(?:[^/\s]+/?)*', sub.command)
        url = sub.command[m.start():m.end()]
        cmd_args = sub.command.split()
        outdir = '-o' in cmd_args
        tvseries = '-t' in cmd_args
        season = '-s' in cmd_args
        program_card = program_card_from_url(url)
        result = f'[drdl3] {index} '

        if tvseries:
            result += f'TV Series: {program_card["SeriesTitle"]}. '
        elif season:
            result += f'Season {program_card["SeasonNumber"]} of {program_card["SeriesTitle"]}. '
        else:
            result += f'{program_card["Title"]} '
        result += 'Output directory: ' + cmd_args[cmd_args.index('-o') + 1] if outdir else 'default'
        print(result)


def add_subscription(args):
    cron = CronTab(user=True)
    job_args = 'dl ' + args.url
    job_args += f' -o {args.outputdir}' if args.outputdir else ''
    job_args += f' -t' if args.tvseries else ''
    job_args += f' -s' if args.season else ''
    job_args += f' >> {os.path.dirname(os.path.abspath(__file__)) + os.sep}log.txt'
    job = cron.new(command=' '.join([os.path.abspath(__file__), job_args]))
    job.setall(f'0 */{args.rate} * * *')
    cron.write()


def remove_subscription(args):
    cron = CronTab(user=True)
    jobs = cron.find_command('drdl3.py')
    jobs = [job for index, job in enumerate(jobs) if index in args.subscriptions]
    for job in jobs:
        cron.remove(job)
    cron.write()


def program_card_from_url(url):
    program_card_url = PROGRAM_CARD_BASE_URL + url[url.rfind('/') + 1:]
    request = requests.get(program_card_url)
    return request.json()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='Sub-command help')

    # Download subparser
    dl_subparser = subparsers.add_parser('dl', help='Download episodes')
    dl_subparser.add_argument('url', help='Url to video from dr.dk/tv')
    dl_subparser.add_argument('-o', '--outputdir', help='Specify output directory')
    dl_subparser.add_argument('-t', '--tvseries', action='store_true', help='Download all available in tv series')
    dl_subparser.add_argument('-s', '--season', action='store_true', help='Download all available in the season')
    dl_subparser.add_argument('--subscribe', action='store_true',
                              help='Subscribe to the episode, season or series.')
    dl_subparser.set_defaults(func=download)

    # List subscriptions subparser
    l_subscription_parser = subparsers.add_parser('lsubs', help='List subscriptions')
    l_subscription_parser.set_defaults(func=list_subscriptions)

    # Add subscription subparser
    a_subscriptions_parser = subparsers.add_parser('add', help='Add new subscription')
    a_subscriptions_parser.add_argument('url', help='Url to video from dr.dk/tv')
    a_subscriptions_parser.add_argument('-o', '--outputdir', help='Specify output directory')
    a_subscriptions_parser.add_argument('-t', '--tvseries', action='store_true', help='Subscribe to the tv series')
    a_subscriptions_parser.add_argument('-s', '--season', action='store_true', help='Subscribe to the season')
    a_subscriptions_parser.add_argument('-r', '--rate', default=2, type=int, nargs='?',
                                        help='Set update rate to every x hours')
    a_subscriptions_parser.set_defaults(func=add_subscription)

    # Remove subscriptions subparser
    r_subscriptions_parser = subparsers.add_parser('rsubs', help='Remove subscriptions')
    r_subscriptions_parser.add_argument('subscriptions', metavar='int', type=int, nargs='+',
                                        help='Index of subscription')
    r_subscriptions_parser.set_defaults(func=remove_subscription)

    # Upcoming releases subparser
    upcoming_parser = subparsers.add_parser('upcoming', help='List upcoming episodes')
    upcoming_parser.add_argument('url', help='Url to video from dr.dk/tv')
    upcoming_parser.set_defaults(func=upcoming)

    args = parser.parse_args()
    args.func(args)
