from .m3u8lib.parser import fetch_playlist_links, construct_file_name_links_map
from .producer_server_process import producer_server_process
from .video_handling_process import video_handling
from .download_process import download_process
from .weblib.parse import construct_headers
from requests.adapters import HTTPAdapter
from hyper.contrib import HTTP20Adapter
from multiprocessing import Process
from traceback import print_exc
from shutil import rmtree
import requests
import argparse
import sys
import os


def directory_validator(string: str) -> str:
    # This code is used to check if passed in headers_path string is valid path to a file
    # if not FileNotFoundError is raised
    if os.path.isfile(string):
        return string
    raise FileNotFoundError(f"{string} does not point to a file")


def main():
    # start the program with -h or --help to get more info on how to use the script.
    parser = argparse.ArgumentParser()
    parser.add_argument("url", help="Pass in a url containing m3u8 playlist", type=str)
    parser.add_argument("-n", "--name", type=str, help="Specify a name to save the downloaded video as, if no name is "
                                                       "specified default name of 'video' will be chosen")
    parser.add_argument("-p", "--header-path", type=directory_validator,
                        help="Specify the path to the file containing headers, if no path is specified the program "
                             "will look for a headers.txt file in the same directory")
    parser.add_argument("-r", "--retry", type=int, help="Specify number of retries by default 5 retries will be "
                                                        "initiated")
    parser.add_argument("-f", "--force", action="store_true", help="If this flag is used and the video has been "
                                                                   "downloaded the download will restart")
    parser.add_argument("-c", "--convert", help="Convert the downloaded video to mp4 using ffmpeg", action="store_true")
    parser.add_argument("-d", "--debug", help="Print helpful messages to the terminal to "
                                              "help understanding the process flow", action="store_true")

    cli_args = parser.parse_args()

    # HTTP/1.1 adapter
    ADAPTER1: HTTPAdapter = HTTPAdapter(max_retries=5)

    # HTTP/2 adapter
    ADAPTER2: HTTP20Adapter = HTTP20Adapter(max_retries=10)

    url = cli_args.url

    if cli_args.name:
        name = cli_args.name
    else:
        name = "video"

    if cli_args.header_path:
        path = cli_args.header_path
    else:
        path = "headers.txt"

    MAX_RETRIES = 5
    if cli_args.retry:
        MAX_RETRIES = cli_args.retry

    headers, http2 = construct_headers(path)

    # Mount new connection adapters to the session created.
    sess: requests.Session = requests.Session()
    parsed_prefix = "/".join(url.split("/")[:-1])
    sess.mount(parsed_prefix, ADAPTER1)
    if http2:
        # Mount a parsed prefix to the session, with HTTP/2 adapter
        sess.mount(parsed_prefix, ADAPTER2)

    links = fetch_playlist_links(sess, url, headers)
    file_link_maps = construct_file_name_links_map(links)
    path_prefix = "." + "".join([i for i in url if i.isalnum()])

    os.makedirs(path_prefix, exist_ok=True)

    try:
        debug = cli_args.debug
        server = Process(target=producer_server_process, args=(debug,), name="producer_server_process")
        video = Process(target=video_handling, args=(len(links), name, cli_args.convert, debug),
                        name="video_handling_process")
        server.start()
        video.start()

        download_process(links, len(links), sess, headers, http2,
                         MAX_RETRIES, cli_args.convert, file_link_maps,
                         path_prefix, debug)

        server.join()
        video.join()
        rmtree(path_prefix)
    except (KeyboardInterrupt, Exception):
        print_exc()

    sys.exit()
