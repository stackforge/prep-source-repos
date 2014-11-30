prep_source_repos
-----------------

Introduction
============

This repository contains scripts for managing multiple outstanding patches
to a gerrit based project. It was initially developed for managing TripleO
deployments, and still makes certain TripleOish assumptions (patches welcome
if you find the tool more generally useful)

The source repo includes:

- tooling to combine arbitrary unmerged gerrit patches (prep_source_repos)
  which will also export an rc file with git refs based on the combined
  branches
- a sample config file that we're using for our TripleO deployments
  (repo_refs.yaml)

Usage
=====

* create a repo_refs.yaml (see the one in the root of this repository
  for inspiration).

* run prep_source_repos $YOUR\_REFS\_FILE $DESTINATIION\_DIR to checkout and
  update the repositories specified by the refs file (in a TripleO context,
  $DESTINATION\_DIR will usually be "$TRIPLEO\_ROOT").

  Note that local edits are saved via git stash whenever you refresh your
  source repos, and restored after the update (which may, of course,
  fail). This provides a convenient way to use local edits / work in
  progress for repositories that are used directly (vs e.g. those that are
  cloned into images).

* (optional) source YOUR_REFS_FILE.variables to configure TripleO scripts to
  use your freshly integrated branches

* proceed with any tripleo activies you might have (building images, deploying,
  etc etc).

Advanced use
============

Refs that don't match the xx/yy/zz form of gerrit refs are presumed to be
local work-in-progress branches. These are not fetched, but are merged into
the rollup branch along with all the other patches. With a little care this
permits working effectively with multiple patchsets in one project without
them being made into a stack in gerrit.

Refs of the form xx/yy/0 are late-bound references to gerrit - they will use
the gerrit REST API to find out the latest version and will use that.

When running prep-source-repos any additional arguments after the refs and
output dir are used to filter the repositories to fetch - so when working on
(say) two local orthogonal patches to nova, and you need to update your
rollup branch just do::

    prep-source-repos foo bar nova

and only nova will be updated.

Related tools
=============

Zuul has a Merger [1]_ class which does something very similar to the
merging aspects of this tool, and a cloner tool [2]_ which does
something similar to the clone-a-bunch-of-repos aspects of this tool.

However, zuul is intended to be used in automated pipelines. The
merger library doesn't do quite what this tool does (although an
attempt to use zuul's merger has been made) [3]_ and the cloner assumes
that a zuul server has already done the merging.

If you're planning to do automated merges as part of an automated
build pipeline, zuul is probably the tool you want to use, not this.

If you're looking for manual checkout-out-and-merge as part of a
manual build process, this tool is probably more suited to your needs.

It would be nice if the two code-bases could merge - or at least, if
this tool could use zuul's library's in future. That doesn't seem
impossible. Patches welcome.

.. [1] http://git.openstack.org/cgit/openstack-infra/zuul/tree/zuul/merger/merger.py
.. [2] http://git.openstack.org/cgit/openstack-infra/zuul/tree/zuul/lib/cloner.py
.. [3] https://review.openstack.org/#/c/137959/
