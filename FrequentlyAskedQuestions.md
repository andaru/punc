# PUNC FAQ #

  * Q: I get a `mercurial.error.Abort: no username supplied` error when running punc.
  * A: The user operating punc (and thus, Mercurial), does not have a `username` attribute in the `[ui]` section of the user's `.hgrc` file.  Create `~$USER/.hgrc` and populate it with the minimum configuration (the `[ui]` and `username` config).
