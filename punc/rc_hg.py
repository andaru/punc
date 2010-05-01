# Copyright 2010 Andrew Fort

import logging
import os

import mercurial.commands
import mercurial.error
import mercurial.hg
import mercurial.ui


class MercurialRevisionControl(object):
    """A wrapper around a Mercurial repository.

    Attributes:
      repo_path: A string, a path (http[s]:// schemes allowed) of the
        repository to push/pull from.
      local_path: A string, a working path, or "check-out" directory.
      options: A dictionary of subclass specific options.
    """

    # The .hgignore file contents.
    HGIGNORE = ('syntax: glob\n\n'
                '.*\n')
    # Files with this percentage similarity or higher will be treated
    # as renames (e.g., rename a router and change just its loopback
    # address, then reflect the change in the Notch device config).
    MOVE_SIMILARITY_PERCENT = 90

    def __init__(self, repo_path=None, local_path=None, **options):
        """A revision control repository.

        The repository should be setup in the _setup_repo() method by
        subclasses.

        Arguments:
          repo_path: A string, the path to the revision control 'master'
            repository path.
          local_path: A string, a working path, or "check-out" directory.
          options: A dictionary of subclass specific options.
        """
        self._ui = mercurial.ui.ui()
        self.repo_path = repo_path
        self.local_path = local_path
        self.options = options
        # Setup the repository.
        self._setup_repo()

    def _setup_repo(self):
        """Sets up the repository ready for operations."""
        self._ui.pushbuffer()
        try:
            dest_repo = None
            if self.repo_path:
                # Attempt to use an existing repo to pull changes to.
                dest_repo = mercurial.hg.repository(self._ui,
                                                    self.local_path)
                logging.info('Pulling updates from master repository %s to %s',
                             self.repo_path, self.local_path)
                try:
                    mercurial.commands.pull(
                        self._ui, dest_repo, source=self.repo_path)
                except mercurial.error.RepoError, e:
                    logging.error('Mercurial error during remote repo pull: %s',
                                  str(e))
                    logging.error('Will continue without remote repository.')
                    self.repo_path = None

            if not self.repo_path:
                # No repository path means no source repository.
                source_repo = None
                # Try to create the destination repository, since it's local.
                if not dest_repo:
                    try:
                        dest_repo = mercurial.hg.repository(self._ui,
                                                            self.local_path,
                                                            create=True)
                        logging.info('Created new Mercurial repository in %s',
                                     self.local_path)
                    except mercurial.error.RepoError, e:
                        if 'already exists' in str(e):
                            logging.info('Opening local repository %s',
                                         self.local_path)
                        else:
                            logging.error('Mercurial error: %s: %s',
                                          e.__class__.__name__,
                                          str(e))

                        # The repository likely already exists, try to open it.
                        try:
                            dest_repo = mercurial.hg.repository(
                                self._ui, self.local_path)
                        except Exception, e:
                            # Something else went wrong, and Mercurial doesn't
                            # have a master Exception subclass.
                            logging.error('Error opening Mercurial repo '
                                          '%r: %s: %s',
                                          self.local_path,
                                          e.__class__.__name__, str(e))

            self._repo = dest_repo
            self._setup_mercurial_data()
        finally:
            self._ui.popbuffer()
        
    def _setup_mercurial_ignore(self):
        try:
            f = open(os.path.join(self.local_path, '.hgignore'), 'w')
            f.write(self.HGIGNORE)
            f.close()
        except (OSError, IOError), e:
            logging.error('Failed to write Mercirial ignore file %r. %s: %s',
                          os.path.join(self.local_path, '.hgignore'),
                          e.__class__.__name__, str(e))
    
    def _setup_mercurial_data(self):
        """Sets up mercurial specific options."""
        if not os.path.exists(os.path.join(self.local_path, '.hgignore')):
            self._setup_mercurial_ignore()      

    def addremove(self):
        """Adds all new files and removes all removed files from repository."""
        self._ui.pushbuffer()
        try:
            try:
                mercurial.commands.addremove(
                    self._ui, self._repo,
                    similarity=self.MOVE_SIMILARITY_PERCENT)
            except Exception, e:
                logging.error('Fatal error during repository operation. '
                              '%s: %s', e.__class__.__name__, str(e))
                raise SystemExit(2)
        finally:
            self._ui.popbuffer()

    def _postcommit(self, unused_changed):
        """Actions to run after the Mercurial commit action."""
        if self.repo_path:
            logging.debug('Pushing Mercurial changes to %s', self.repo_path)
            mercurial.commands.push(self._ui, self._repo, dest=self.repo_path)

    def commit(self, paths=None, message=None, exclude=None):
        """Commits paths in the repository with an optional commit message."""
        self._ui.pushbuffer()
        try:
            try:
                (modified, added, removed, deleted, unused_unknown,
                 unused_ignored, unused_clean) = self._repo.status()
                if unused_unknown:
                    logging.debug('Unknown: %r', unused_unknown)
                if unused_ignored:
                    logging.debug('Ignored: %r', unused_ignored)
                if unused_clean:
                    logging.debug('Cleaned: %r', unused_clean)
            except Exception, e:
                logging.error('Failed to check repository status. '
                              'Check repository status. Error: %s: %s',
                              e.__class__.__name__, str(e))
                raise SystemExit(2)
                
            if not (
                len(modified) or len(added) or len(removed) or len(deleted)):
                logging.info('No changes; '
                             'nothing commited to mercurial repository.')
                changes = False
            else:
                changes = True
                if message is None:
                    deets = []
                    num_added = len(added)
                    num_modified = len(modified)
                    num_removed = len(removed)
                    if num_added:
                        deets.append('%d adds' % num_added)
                    if num_modified:
                        deets.append('%d changes' % num_modified)
                    if num_removed:
                        deets.append('%d deletes' % num_removed)
                    deets = ' '.join(sorted(deets))
                    msg = ['Network configuration change: %s\n' % deets]
                    if num_added:
                        msg.append('%d new devices: %s' % (
                                num_added, ' '.join(
                                    [os.path.basename(a) for a in added])))
                    if num_modified:
                        msg.append('%d devices changed: %s' % (
                                num_modified, ' '.join(
                                    [os.path.basename(m) for m in modified])))
                    if num_removed:
                        msg.append('%d devices removed: %s' % (
                                num_removed, ' '.join(
                                    [os.path.basename(r) for r in removed])))
                    message = '\n'.join(msg)
                    logging.info(message)

            if paths:
                mercurial.commands.commit(self._ui, self._repo, paths,
                                          exclude=exclude, message=message)
            else:
                mercurial.commands.commit(self._ui, self._repo, exclude=exclude,
                                          message=message)
            self._postcommit(changes)
        finally:
            self._ui.popbuffer()
