#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
"""Agent Cisco Prime
Write cisco_prime_ sections containing JSON formatted results from Cisco Prime API
"""

import argparse
import json
import logging
import sys
from collections.abc import Sequence

import requests
import urllib3

from cmk.special_agents.v0_unstable.misc import vcrtrace
from cmk.utils import password_store

API_PATH = "webacs/api/v1/data/"
REQUESTS = {
    "wifi_access_points": "AccessPoints.json?.full=true&.nocount=true&.maxResults=10000",
    "wifi_connections": "ClientCounts.json?.full=true&subkey=ROOT-DOMAIN&type=SSID",
    "wlan_controller": "WlanControllers.json?.full=true",
}


def parse_arguments(argv: Sequence[str]) -> argparse.Namespace:
    """Parse arguments needed to construct an URL and for connection conditions"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--hostname", required=True, help="Host to query")
    parser.add_argument("--port", "-p", type=int, help="IPv4 port to connect to")
    parser.add_argument("--basic-auth", "-u", type=str, help="username:password for basic_auth")
    parser.add_argument("--no-tls", action="store_true", help="Use http instead of https")
    parser.add_argument("--no-cert-check", action="store_true")
    parser.add_argument(
        "--timeout",
        "-t",
        type=float,
        default=20,
        help="API call timeout in seconds",
    )
    parser.add_argument("--debug", action="store_true", help="Keep some exceptions unhandled")
    parser.add_argument("--verbose", "-v", action="count", default=0)
    parser.add_argument("--vcrtrace", action=vcrtrace(filter_headers=[("authorization", "****")]))
    return parser.parse_args(argv)


def write_section_from_get_request(argv: Sequence[str]) -> None:
    """Writes `cisco_prime_` sections (currently only `connections`) containing the results of
    GET requests on the provided url.
    """

    def setup_logging(verbose: bool) -> None:
        logging.basicConfig(
            level={0: logging.WARN, 1: logging.INFO, 2: logging.DEBUG}.get(verbose, logging.DEBUG),
        )
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        logging.getLogger("urllib3.connectionpool").setLevel(logging.INFO)
        logging.getLogger("vcr").setLevel(logging.WARN)

    def fetch_json_data(url: str, args: argparse.Namespace) -> str:
        """
        Cisco allows the user to configure the rate limiting parameters. We currently assume that
        the default parameters are in place for some.

        Docs:
            * https://developer.cisco.com/site/prime-infrastructure/documents/api-reference/rest-api-v3-9/v4/@id=rate-limiting-doc/#rate-limiting-config-doc
            * https://developer.cisco.com/site/prime-infrastructure/documents/api-reference/rest-api-v3-9/v4/@id=tutorials/ (see Paging section)
        """
        logging.info("fetch data from url=%r", url)

        if args.basic_auth:
            username, password = args.basic_auth.split(":")
            auth = (username, password)
        else:
            auth = None
        response = requests.get(
            url=url,
            auth=auth,
            timeout=args.timeout,
            verify=not args.no_cert_check,
        )
        response.raise_for_status()
        try:
            # Parse JSON and dump it again in order to validate the string and get rid of unneeded
            # whitespace characters and newlines
            return json.dumps(json.loads(response.text))
        except json.JSONDecodeError as exc:
            # Translate exception into more generic exception we can handle from outside without
            # having to import `json` everywhere. This should be turned into s.th. like
            #    raise OurCustomException("Nice message") [from exc]
            # as soon as we have proper exception handling
            raise RuntimeError(
                f"Server dit not return valid JSON ({exc.msg}). Reply with {response.text[:30]!r}"
            )

    args = parse_arguments(argv)
    setup_logging(args.verbose)
    logging.debug("cmd: argv=%r, turned into: %r", argv, args.__dict__)
    try:
        url_prefix = "{}://{}{}/{}".format(
            "http" if args.no_tls else "https",
            args.hostname,
            ":%s" % args.port if args.port else "",
            API_PATH,
        )
        for service, request_string in REQUESTS.items():
            sys.stdout.write(
                "<<<cisco_prime_%s:sep(0)>>>\n%s\n"
                % (
                    service,
                    fetch_json_data(url_prefix + request_string, args),
                )
            )

    except Exception as exc:
        if args.debug:
            raise
        # In the non-debug case the first (and only) line on stderr should tell what happended
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(-1)


def main(argv: Sequence[str] | None = None) -> None:
    """Just replace password placeholders in command line args and call
    write_section_from_get_request()"""
    if argv is None:
        password_store.replace_passwords()
        argv = sys.argv[1:]

    write_section_from_get_request(argv)


if __name__ == "__main__":
    main()
