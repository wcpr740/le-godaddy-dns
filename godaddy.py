#!/usr/bin/env python3

import os
import sys
import shutil
import subprocess
import logging
import godaddypy

if "GD_KEY" not in os.environ:
    raise Exception("Missing Godaddy API-key in GD_KEY environment variable! Please register one at https://developer.godaddy.com/keys/")

if "GD_SECRET" not in os.environ:
    raise Exception("Missing Godaddy API-secret in GD_SECRET environment variable! Please register one at https://developer.godaddy.com/keys/")

PVE_NODE_DIR = '/etc/pve/nodes/'

api_key = os.environ["GD_KEY"]
api_secret = os.environ["GD_SECRET"]
my_acct = godaddypy.Account(api_key=api_key, api_secret=api_secret)
client = godaddypy.Client(my_acct)

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)


def _get_zone(domain):
    parts = domain.split(".")
    zone_parts = parts[-2::]
    zone = ".".join(zone_parts)
    return zone


def _get_subdomain_for(domain, zone):
    subdomain = domain[0:(-len(zone)-1)]
    return subdomain


def _update_dns(domain, token):
    challengedomain = "_acme-challenge." + domain
    logger.info(" + Updating TXT record for {0} to '{1}'.".format(challengedomain, token))
    zone = _get_zone(challengedomain)
    # logger.info("Zone to update: {0}".format(zone))
    subdomain = _get_subdomain_for(challengedomain, zone)
    # logger.info("Subdomain name: {0}".format(subdomain))

    record = {
        'name': subdomain,
        'data': token,
        'ttl': 600,
        'type': 'TXT'
    }
    result = client.update_record(zone, record)
    if result is not True:
        logger.warn("Error updating record for domain {0}.".format(domain))


def create_txt_record(args):
    domain, token = args[0], args[2]
    _update_dns(domain, token)


def delete_txt_record(args):
    domain = args[0]
    # using client.delete_record() is dangerous. null it instead!
    # https://github.com/eXamadeus/godaddypy/issues/13
    _update_dns(domain, "null")


def deploy_cert(args):
    domain, privkey_pem, cert_pem, fullchain_pem, chain_pem, timestamp = args

    logger.info(' + ssl_certificate: {0}'.format(fullchain_pem))
    logger.info(' + ssl_certificate_key: {0}'.format(privkey_pem))

    # copy certs to each node
    for node in os.listdir(PVE_NODE_DIR):
        if not os.path.isdir(os.path.join(PVE_NODE_DIR, node)):
            continue  # only use real nodes... in case there are random files in the folder

        shutil.copy(fullchain_pem, os.path.join(PVE_NODE_DIR, node, 'pveproxy-ssl.pem'))
        shutil.copy(privkey_pem, os.path.join(PVE_NODE_DIR, node, 'pveproxy-ssl.key'))

    # restart PVE
    subprocess.call('systemctl restart pveproxy', shell=True)

    return


def unchanged_cert(args):
    return


def main(argv):
    ops = {
        'deploy_challenge': create_txt_record,
        'clean_challenge' : delete_txt_record,
        'deploy_cert'     : deploy_cert,
        'unchanged_cert'  : unchanged_cert,
    }
    logger.info(" + Godaddy hook executing: {0}".format(argv[0]))
    ops[argv[0]](argv[1:])


if __name__ == '__main__':
    main(sys.argv[1:])
