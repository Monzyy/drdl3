#!/usr/bin/env python3

import argparse
import glob
import os
import re
import shutil
from datetime import datetime

import requests
import youtube_dl
from crontab import CronTab
from dateutil.parser import parse

PROGRAM_CARD_BASE_URL = 'https://www.dr.dk/mu-online/api/1.4/programcard/'
OLD_PC_BASE_URL = 'https://www.dr.dk/mu/programcard/'
BUNDLE_BASE_URL = 'https://www.dr.dk/mu/bundle/'


def program_card_from_url(url):
    program_card_url = PROGRAM_CARD_BASE_URL + url[url.rfind('/') + 1:]
    request = requests.get(program_card_url)
    return request.json()


def trim_title(title):
    title = title.replace('\'', '').replace('-', '')
    title = re.sub(r'\s+', ' ', title)
    return title.replace(' ', '.')


def get_plex_filename(episode):
    request = requests.get(OLD_PC_BASE_URL + episode.get('Urn'))
    episode_data = request.json().get('Data')[0]
    title = trim_title(episode_data.get('Broadcasts')[0].get('OriginalTitle', episode.get('SeriesTitle')))
    season_number = episode_data.get('SeasonNumber', 1)
    episode_number = episode_data.get('EpisodeNumber')
    return f'{title}.S{season_number:02}E{episode_number:02}'


def get_slug_plex_path_from_episode(episode, tvshow_dir):
    request = requests.get(OLD_PC_BASE_URL + episode.get('Urn'))
    episode_data = request.json().get('Data')[0]
    original_title = trim_title(episode_data.get('Broadcasts')[0].get('OriginalTitle', episode.get('SeriesTitle')))
    season_number = episode_data.get('SeasonNumber', 1)
    episode_number = episode_data.get('EpisodeNumber')
    if tvshow_dir:
        path = os.path.join(args.outputdir, original_title, f'Season{season_number:02}',
                            f'{original_title}.S{season_number:02}E{episode_number:02}')
    else:
        path = os.path.join(args.outputdir, f'{original_title}.S{season_number:02}E{episode_number:02}')
    return {episode.get('Slug'): path}


def download(args):
    args.outputdir = os.path.expanduser(args.outputdir)
    # Get program card
    url = args.url
    program_card = program_card_from_url(url)
    dl_url_list = []
    item_to_path = {}
    if program_card.get('PresentationUri'):
        dl_url_list.append(program_card.get('PresentationUri'))
        if args.plexify:
            item_to_path = {**item_to_path, **get_slug_plex_path_from_episode(program_card, tvshow_dir=False)}

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
                    if args.plexify:
                        item_to_path = {**item_to_path, **get_slug_plex_path_from_episode(episode, tvshow_dir=True)}

    ydl_opts = {
        'write_all_thumbnails': True,
        'writesubtitles': True,
        'restrictfilenames': True,
        'noprogress': True,
        'download_archive': 'youtube-dl-archive.txt'
    }
    if args.plexify:
        ydl_opts['outtmpl'] = '%(id)s.%(ext)s'
    if not dl_url_list:
        print('[drdl3] no episodes available')
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download(dl_url_list)

    if args.plexify:
        for item, target_path in item_to_path.items():
            for src_file in glob.glob(f'{item}*'):
                target_dir = os.path.dirname(target_path)
                extension = os.path.splitext(src_file)[1]
                if not os.path.exists(target_dir):
                    print(f'[drdl3] Creating directory {target_path}')
                    os.makedirs(target_dir)
                print(f'[drdl3] Moving {src_file} to {target_path + extension}')
                shutil.move(src_file, target_path + extension)

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

    if not members:
        print('[drdl3] No upcoming episodes found')
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
    args.outputdir = os.path.expanduser(args.outputdir)
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


def list_available(args):
    program_card = program_card_from_url(args.url)
    series_urn = program_card.get('SeriesUrn')
    series_url = 'https://www.dr.dk/mu-online/api/1.4/list/view/seasons?id=' + series_urn + '&limit=0'
    request = requests.get(series_url)
    series_data = request.json()
    for season in series_data.get('Items'):
        for episode in season.get('Episodes').get('Items'):
            title = episode.get('Title')
            plex_title = get_plex_filename(episode)
            duration = episode.get('PrimaryAsset').get('DurationInMilliseconds') / 60000
            print(f'[drdl3] Title: {title}\tPlex title: {plex_title}.mp4\tDuration: {duration:.2f} min')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='Sub-command help')

    # Download subparser
    dl_subparser = subparsers.add_parser('dl', help='Download episodes')
    dl_subparser.add_argument('url', help='Url to video from dr.dk/tv')
    dl_subparser.add_argument('-o', '--outputdir', help='Specify output directory', default=os.getcwd())
    dl_subparser.add_argument('-t', '--tvseries', action='store_true', help='Download all available in tv series')
    dl_subparser.add_argument('-s', '--season', action='store_true', help='Download all available in the season')
    dl_subparser.add_argument('-p', '--plexify', action='store_false',
                              help='Disable plexify and use youtube-dl\'s default title format')
    dl_subparser.add_argument('--subscribe', action='store_true',
                              help='Subscribe to the episode, season or series')
    dl_subparser.set_defaults(func=download)

    # List subscriptions subparser
    l_subscription_parser = subparsers.add_parser('lsubs', help='List subscriptions')
    l_subscription_parser.set_defaults(func=list_subscriptions)

    # Add subscription subparser
    a_subscriptions_parser = subparsers.add_parser('add', help='Add new subscription')
    a_subscriptions_parser.add_argument('url', help='Url to video from dr.dk/tv')
    a_subscriptions_parser.add_argument('-o', '--outputdir', help='Specify output directory', default=os.getcwd())
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

    l_available_parser = subparsers.add_parser('list', help='List available in series')
    l_available_parser.add_argument('url', help='Url to video in series from dr.dk/tv')
    l_available_parser.set_defaults(func=list_available)

    args = parser.parse_args()
    args.func(args)
