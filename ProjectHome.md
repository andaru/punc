![http://www.enemesco.net/notch/_static/punc.jpg](http://www.enemesco.net/notch/_static/punc.jpg)

## punc : bacon saving for network engineers ##
**punc** is a network element configuration backup tool. It's an "alternative" to the [RANCID](http://www.shrubbery.net/rancid) network configuration collector. In reality, alternative means we collect far fewer commands on far fewer platforms. However, input can be manipulated in any way you see fit, and it's written in Python.  So maybe that ticks some boxes you wanted ticked, instead.

Punc's short code and straight-forward programming style ("[crappy](http://www.google.com/search?q=perfect+is+the+enemy+of+done+stephen+stuart+crappy)") encourages modification by a wide range of users, and since [it uses the Notch system](http://code.google.com/p/notch) to talk to devices, it can be distributed easily across your network to scale to large numbers of devices on a frequent backup schedule.

### setup? ###

To get the current release version, use pip or easy\_install:
```
$ pip install punc
```

Note that you must have [Notch](http://code.google.com/p/notch) pre-installed to be able to use punc to get data from your routers and switches.

If you'd like the development version, you'll need to drive a [Mercurial](http://mercurial.selenic.com/) client:

```
$ hg clone https://punc.googlecode.com/hg punc
$ cd punc
$ python ./setup.py install
```

To use punc:

```
# Inspect the config file and modify the output path (Punc will create that path for you when executed).

$ less ./conf/punc-simple.yaml

# Start the collector, pointing it at your Notch Agent or agents, collecting 'all' collections.

$ punc -f ./conf/punc-simple.yaml --debug -c all -a localhost:8080

$ punc -f ./conf/punc-simple.yaml --debug -c all -a notch.example.com:8080 -a notch.example.com:8081 -a notch.example.com:8082

# Output is rooted at the base_path from your configuration file
# This defaults to /tmp/punc-workdir/
```