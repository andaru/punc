# Copyright 2010 Andrew Fort

import logging
import os

import mercurial.commands
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
            if self.repo_path:
                source_repo, dest_repo = mercurial.hg.clone(self.repo_path,
                                                            self.local_path,
                                                            update=True)
            else:
                # No repository path means no source repository.
                source_repo = None
                # Try to create the destination repository, since it's local.
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

                    # The repository likely already exists, so try to open it.
                    try:
                        dest_repo = mercurial.hg.repository(
                            self._ui, self.local_path)
                    except mercurial.error.Error, e:
                        # Something else went wrong.
                        logging.error('Mercurial error opening repo '
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
            mercurial.commands.addremove(
                self._ui, self._repo,
                similarity=self.MOVE_SIMILARITY_PERCENT)
        finally:
            self._ui.popbuffer()
        
    def commit(self, paths=None, message=None, **options):
        """Commits paths in the repository with an optional commit message."""
        self._ui.pushbuffer()
        try:
            (modified, added, removed, deleted, unused_unknown,
             unused_ignored, unused_clean) = self._repo.status()
            if not (
                len(modified) or len(added) or len(removed) or len(deleted)):
                logging.info('No changes; '
                             'nothing commited to mercurial repository.')
            else:
                if message is None:
                    message = 'Configuration changes detected:\n'
                    if len(added):
                        message += ' %d new routers: %s' % (
                            len(added), ' '.join(
                                [os.path.basename(a) for a in added]))
                    if len(modified):
                        message += '\n %d routers modified: %s' % (
                            len(modified), ' '.join(
                                [os.path.basename(m) for m in modified]))
                    if len(removed):
                        message += '\n %d routers removed: %s' % (
                            len(removed), ' '.join(
                                [os.path.basename(r) for r in removed]))
                    logging.info(message)

            if paths:
                mercurial.commands.commit(self._ui, self._repo, paths,
                                          message=message)
            else:
                mercurial.commands.commit(self._ui, self._repo,
                                          message=message)
        finally:
            self._ui.popbuffer()
