# Cartboy, the universal restarter

## What?
Cartboy is a python script that tries to be a more or less universal restarter for any sort of application.

Surely there must be some better alternatives out there but I strongly believe that reinventing the wheel once in a while can't really hurt.
Applications fail and sometimes crash, that is inevitable. Of course you should debug and resolve the issue but this is not always possible and sometimes the only solution is an "autorestarter".
And this is exactly where cartboy comes in. Why choose cartboy?
Main strengths:
* extensive logging 
* easy to set up, you don't need to know python to use cartboy
* very flexible, you can configure different actions for status checking and starting of applications easily

Configuration is held in /etc/cartboy. Currently this means just the "/etc/cartboy/applications" directory, but this will change in future.

Cartboy debian package also installs a cron script in /etc/cron.d/cartboy that executes cartboy.py once per minute by default.

Log file is written to /var/log/cartboy.log and it is quite extensive by default, so you should probably set up some sort of log rotation (logrotate script is not included in the cartboy package at the moment).

## Installation

	dpkg -i cartboy.deb

yes, that is it


## Configuration 

Configuration files live in /etc/cartboy and individual applications are defined in /etc/cartboy/applications, 
each application directory has to contain 2 scripts: *pid* and *start* and it can optionally also 
contain a file *name* which, as you might guess, will be used to set application name 
(by default application name is the name of the directory) and it can also contain optional file *alert* 
that will be executed if cartboy fails to start the application for several times, more on that later.

### Quick configuration example
Lets look at an example to better illustrate the minimal configuration.
So lets say we have Nginx installed and we want to set up an autorestarter for it.

Create a directory for it 
	mkdir /etc/cartboy/applications/nginx
now set up the minimal set of scripts for it
	echo "cat /var/run/nginx.pid" >  /etc/cartboy/applications/nginx/pid
	echo "/etc/init.d/nginx start" >  /etc/cartboy/applications/nginx/start
That's it. It really is that simple. 
If you want to, you can also optionally provide a better name for the application like so:
	echo "Nginx web server" > /etc/cartboy/applications/nginx/name

### More details on configuration

Lets look at all the application files that you can set up.

* _pid_ - this script has to return the PID of the application. 
	If the applications has a pidfile, then you can just __cat__ it like so `cat /var/run/nginx.pid`, 
	if it does not have a pidfile, you can use, for example, __pgrep__ like so `pgrep -f "nginx: master process"`. 
	It does not really matter how you do it as long as your script returns a PID. 
* _start_ - this, as you can probably guess, is the script that will be executed in order to start the application. 
	Again, this can be anything, as long as it gets the job done.
* _name_ - this is just a text file containing the name of the application. It can contain whitespaces. Only the first line of the file will be read.
* _alert_ - this script will be executed if Cartboy fails to start the application for 3 times (can be overriden in the configuration). 
	This can be quite usefull when the application misbehaves. Depending on what sort of monitoring system you use this script can create some 
	file that will be read by your monitorins system agent or can, for example, send an email to you. 
	Again, as with all the previous files, it really is up to the sysadmin to decide if this functionality is necessary and what to do with it.

## How does it work?

Quite simple, really. Cartboy is executed from crontab, it checks all the directories under /etc/cartboy/applications 
to find any apps that are configured for autorestarting. it does some simple validation just to check if the minimal set of files exists for every application.
For every application cartboy:
	
	* executes the _pid_ file to get the pid
	* checks the processlist to see if the apllication is running
	* if it is running then that's it for this application
	* if the application is not running, cartboy checks if it has already tried starting it up
		by default cartboy will try to start an application for 3 consecutive times, after that a _backoff_ time will kick in, where there will be no more tries to start it for the duration of this time.
	* if the application fails to start for more than 10 consecutive times, cartboy will increase the backoff time 10 times
	* if application is started up successfully cartboy resets the failure counter
