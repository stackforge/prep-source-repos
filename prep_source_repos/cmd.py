#!/usr/bin/env python

import argparse
import json
import logging
import os.path
import re
from subprocess import check_call, check_output
import sys

import yaml

import requests
import zuul.merger.merger
import zuul.model

logging.basicConfig(level=logging.DEBUG)

def normalise_conf(conf):
    """generate full paths etc for easy application later.

    The resulting structure is:
    basename -> (remotebase, gerrit_API_base).
    """
    def make_repos(thing, path_stack):
        if isinstance(thing, dict):
            repos = {}
            for key, subthing in thing.items():
                path = path_stack + (key,)
                repos.update(make_repos(subthing, path))
            return repos
        elif isinstance(thing, list):
            path = '/'.join(path_stack)
            repos = {}
            for name in thing:
                if name in repos:
                    raise ValueError("%r defined multiple times" % name)
                repos[name] = ('%s/%s' % (path, name), path_stack[0])
            return repos
        else:
            raise ValueError("%r is not a dict or list" % (thing,))
    conf['repos'] = make_repos(conf['repos'], ())
    return conf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("refs", help="the yaml config file")
    parser.add_argument("output", help="where to put the downloaded repositories")
    parser.add_argument("repos", help="what repos to update", nargs="*")
    args = parser.parse_args()
    SRC_ROOT = os.path.abspath(args.output)
    with open(args.refs, 'rt') as arg_file:
        CONF = yaml.safe_load(arg_file.read())
    CONF = normalise_conf(CONF)
    extra_config = CONF['config']

    variables = []
    session = requests.Session()
    session.headers = {'Accept': 'application/json', 'Accept-Encoding': 'gzip'}
    resolved_refs = {}

    merger = zuul.merger.merger.Merger(SRC_ROOT,
                                       extra_config['ssh_key'], extra_config['email'],
                                       extra_config['username'])

    for repo, (remote, gerrit) in CONF['repos'].items():
        if args.repos and repo not in args.repos:
            continue
        rd = os.path.join(SRC_ROOT, repo)
        git_repo = merger.addProject(repo, remote)
        git_repo.update()

        refs = CONF['gerrit_refs'].get(repo, ())

        git_refs = ['+master:review/master']
        for ref in refs:
            segments = ref.split('/')
            if len(segments) != 3:
                # Weak heuristic, may need fixing.
                continue
            if segments[2] == '0':
                # pull the latest edition
                gerrit_url = gerrit + ('/changes/?q=%s&o=CURRENT_REVISION'
                    % segments[1])
                details = json.loads(session.get(gerrit_url).text[4:])
                src = details[0]['revisions'].values()[0]['fetch'].values()[0]
                rref = src['ref']
                print("Resolved ref %s to %s" % (ref, rref))
                resolved_refs[ref] = rref
            else:
                rref = 'refs/changes/%(ref)s' % dict(ref=ref)

            git_refs.append(
                '+%(rref)s:%(rref)s' % dict(rref=rref))
        print 'fetching from %s %s' % (remote, git_refs)
        check_call(['git', 'fetch', remote] + git_refs, cwd=rd)

        if not refs:
            branch_name = 'master'
        else:
            components = []
            for ref in refs:
                segments = ref.split('/')
                if len(segments) == 3:
                    components.append(segments[1])
                else:
                    components.append(ref)
            branch_name = 'rollup_' + '_'.join(components)
        dirty = check_output(['git', 'status', '-z', '-uno'], cwd=rd)
        if dirty:
            check_call(['git', 'stash'], cwd=rd)
        branches = check_output(['git', 'branch', '-a'], cwd=rd)
        if ' ' + branch_name in branches:
            print 'Resetting existing branch %s...' % branch_name
            check_call(['git', 'checkout', branch_name], cwd=rd)
            check_call(['git', 'reset', '--hard', 'review/master'], cwd=rd)
        else:
            check_call(['git', 'checkout', '-b', branch_name, 'review/master'], cwd=rd)

        merge_items = []

        for ref in refs:
            segments = ref.split('/')
            if len(segments) == 3:
                if ref in resolved_refs:
                    ref = resolved_refs[ref]
                else:
                    ref = 'refs/changes/%s' % ref
            print 'merging in %s' % ref
            merge_item = { "number": ref.split('/')[1], "patchset":
                           ref.split('/')[2], "project": repo, "url": remote,
                           "branch": branch_name, 'refspec': ref, 'ref': ref,
                           "merge_mode": zuul.model.MERGER_CHERRY_PICK }
            merge_items.append(merge_item)

        if merge_items:
            merger.mergeChanges(merge_items)

        if dirty:
            check_call(['git', 'stash', 'pop'], cwd=rd)
        normalised_repo = re.sub('[^A-Za-z0-9_]', '_', repo)
        if repo not in CONF['gerrit_refs']:
            print 'no refs for %s' % repo
            variables.append((normalised_repo, rd, None))
        else:
            variables.append((normalised_repo, rd, branch_name))

    with open(args.refs + '.variables', 'wt') as output:
        for name, location, ref in variables:
            output.write('export DIB_REPOTYPE_%s=git\n' % name)
            output.write('export DIB_REPOLOCATION_%s=%s\n' % (name, location))
            if ref:
                output.write('export DIB_REPOREF_%s=%s\n' % (name, ref))
            else:
                output.write('unset DIB_REPOREF_%s\n'% name)
    return 0
