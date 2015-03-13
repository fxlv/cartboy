#!/usr/bin/env python
import sys
import argparse
import time
import logging
import pickle
import glob
import os
import re
import datetime
from fcntl import flock, LOCK_EX, LOCK_NB
from subprocess import *

try:
    import psutil
except:
    print "\nPlease install psutil\nOn debian this means installing python-psutil package\n\n"
    sys.exit(1)

############### Config #######################

lock_file_name = "/var/lock/cartboy.lock"
log_file = "/var/log/cartboy.log"
history_file = "/var/lib/cartboy/history"
max_start_fails = 4
max_start_fails2 = 10
backoff_time = 10  # 60 seconds

##############################################

p = argparse.ArgumentParser(description="Cartboy, the universal restarter")
# p.add_argument("--test",action="store_true",help="Test autorestarter execution")
p.add_argument("--debug", action="store_true")
args = p.parse_args()

class Store:
    def __init__(self, data_type="history"):
        self.data = False
        self.data_type = data_type
        logging.info("Initializing '{0}' Store".format(self.data_type))
        if data_type == "history":
            self.savefile = history_file
        # FIXME: either user or remove this
        # elif data == "rates_history":
        #    self.savefile=lib.conf.rates_savefile
        else:
            raise Exception("Invalid data specified for Store")

    def save(self):
        logging.info("Saving data")
        try:
            with open(self.savefile, 'wb') as sfile:
                pickle.dump(self.data, sfile)
        except IOError:
            logging.critical("Unable to write data to savefile - {0}".format(savefile))
            logging.critical("Please check the settings and make sure this file is in a writable location")
            sys.exit(1)

    def load(self):
        logging.info("Loading '{0}' data".format(self.data))
        try:
            with open(self.savefile, 'rb') as sfile:
                data = pickle.load(sfile)
                data_length = len(data)
                logging.debug("loaded data: %s length: %s", data, data_length)
                logging.debug("Raw loaded data: %s", data)
        except IOError:
            logging.warning("Unable to load previous data")
            data = {} # if we cannot load previous data, this is not critical, return empty dictionary
        self.data = data

    def increment_failcount(self, app_name):
        self.load()
        current_failcount = self.get_failcount(app_name)
        new_failcount = current_failcount+1
        mainlog.debug("Incrementing failcount for application '{0}', {1} -> {2}".format(app_name,current_failcount,new_failcount))
        self.set_failcount(app_name, new_failcount, False)

    def set_failcount(self,app_name,failcount,status=True):
        self.load()
        mainlog.debug("Setting failcount for application '{0}' to {1}".format(app_name,failcount))
        try:
            self.data[app_name]={'failcount':failcount,'status':status,'time':datetime.datetime.now()}
            self.save()
        except:
            mainlog.warning("Unable to set failcount for application '{0}', savefile corrupt?".format(app_name))

    def reset_failcount(self,app_name):
        self.load()
        mainlog.debug("Resetting failcount for application '{0}'".format(app_name))
        self.set_failcount(app_name, 0)
        self.save()

    def get_failcount(self, app_name):
        self.load()
        mainlog.debug("Getting failcount for application '{0}'".format(app_name))
        if app_name in self.data:
            try:
                failcount=int(self.data[app_name]['failcount']) # if for whatever reason failcount is not an integer, the script goes boom
            except:
                mainlog.warning("Unable to get the failcount for application '{0}', the store appears to be corrupt.".format(app_name))
                failcount = 0
        else:
            failcount = 0
        return failcount

    def get_last_time(self,app_name):
        last_time = False
        self.load()
        if app_name in self.data:
            try:
                last_time=self.data[app_name]['time']
            except:
                mainlog.warning("Unable to get last time for application '{0}'".format(app_name))
        return last_time

    def get_last_status(self, app_name):
        last_status = False
        self.load()
        if app_name in self.data:
            try:
                last_status=self.data[app_name]['status']
            except:
                mainlog.warning("Unable to get last status for application '{0}'".format(app_name))
        return last_status

    def dump(self):
        self.load()
        print self.data


def die(msg=False):
    mainlog.debug("die() function called")
    if msg:
        print "ERROR: {0}".format(msg)
        mainlog.critical(msg)
    sys.exit(1)


def usage():
    mainlog.info("Displaying usage information")
    p.print_help()
    sys.exit(0)


def lock():
    # try to acquire a non-blocking exclusive lock on a file.
    # exit in case of failure.
    # there is no need to unlock the file as python will do it for us
    try:
        mainlog.debug("Opening lock file")
        lock_file = open(lock_file_name,'w')
    except IOError:
        die("Unable to open the lock file.")
    try:
        mainlog.debug("Locking...")
        flock(lock_file, LOCK_EX | LOCK_NB)
        # return lock_file object to caller, otherwise python will close it
        return lock_file
    except IOError:
        die("Unable to acquire lock on {0}".format(lock_file_name))


def execute(cmd_name):
    cmdlist = []
    for arg in cmd_name.split():
        cmdlist.append(arg)
    mainlog.debug("Executing command {0}".format(cmd_name))
    cmd = Popen(cmdlist, stdout=PIPE, stderr=PIPE)
    mainlog.debug("Returning result")
    return cmd.stdout.readlines()


def get_pid(app):
    mainlog.debug("get_pid() called")
    cmd = "{0}/pid".format(app)
    try:
        result = execute("sh {0}".format(cmd))
    except:
        mainlog.debug("Execution of '{0}' failed".format(cmd))
        return False
    if not len(result) == 1 or not len(result[0].split()) == 1:
        mainlog.debug("Execution of '{0}' returned an unexpected result".format(cmd))
        return False
    try:
        pid = int(result[0])
        return pid
    except:
        mainlog.debug("Invalid PID returned")
        return False


def is_running(pid):
    mainlog.debug("is_running() called")
    return pid in [p.pid for p in psutil.get_process_list()]


def get_all_apps():
    mainlog.debug("get_all_apps() called")
    apps = glob.glob("applications/*")
    if len(apps) > 0:
        return apps
    else:
        return False

def valid_app(app_path):
    # check if 'app' directory contains pid and start scripts
    if not os.path.exists("{0}/pid".format(app_path)):
        mainlog.warning("Application: '{0}' is missing its 'pid' script".format(app_path))
        return False
    if not os.path.exists("{0}/start".format(app_path)):
        mainlog.warning("Application: '{0}' is missing its 'start' script".format(app_path))
        return False
    return True


def get_app_name(app_path):
    if os.path.exists("{0}/name".format(app_path)):
        app_name = open("{0}/name".format(app_path)).readline().strip()
        if not re.match("\w+", app_name):
            die("Invalid application name provided for {0}".format(app_path))
        mainlog.debug("Found application name: {0}".format(app_name))
    else:
        app_name=app_path.split("/")[1]
        mainlog.debug("Setting application name to: {0}".format(app_name))
    return app_name

def start_application(app_path):
    local_backoff_time = backoff_time
    history = Store('history')
    app_name = get_app_name(app_path)
    failcount = history.get_failcount(app_name)
    if failcount >= max_start_fails:
        if failcount >= max_start_fails2:
            local_backoff_time = backoff_time*10
        time_now = datetime.datetime.now()
        last_status = history.get_last_status(app_name)
        last_time = history.get_last_time(app_name)
        if not last_time: die("Unable to get last time for application '{0}', corrupted history file?".format(app_name))
        backoff_time_elapsed = time_now-last_time
        if not backoff_time_elapsed.seconds > local_backoff_time:
            wait_time_till_next_start = local_backoff_time-backoff_time_elapsed.seconds
            mainlog.warning("Starting of application '{0}' has failed {1} times, skipping.".format(app_name,failcount))
            mainlog.warning("The next attempted startup of this application will be made after {0} seconds".format(wait_time_till_next_start))
            print "last status:", last_status
            print "last time:", last_time
            if os.path.exists("{0}/alert".format(app_path)):
                mainlog.debug("Executing the alert for application '{0}'".format(app_name))
                print execute("sh {0}/alert".format(app_path))
            return False
    mainlog.debug("Exec output: {0}".format(execute("sh {0}/start".format(app_path))))
    time.sleep(1)
    if get_pid(app_path):
        mainlog.debug("Application {0} started successfully".format(app_name))
        history.reset_failcount(app_name)
    else:
        mainlog.debug("Failed to start {0}".format(app_name))
        history.increment_failcount(app_name)

# initialize logging
if args.debug:
    log_level = logging.DEBUG
else:
    log_level = logging.INFO

mainlog = logging.getLogger("Cartboy")

mainlog.setLevel(logging.DEBUG)

filelog = logging.FileHandler(log_file)
filelog.setLevel(logging.DEBUG)
consolelog = logging.StreamHandler()
consolelog.setLevel(log_level)
formatter = logging.Formatter("%(asctime)s %(levelname)s [ %(name)s ] %(message)s",'%d.%m.%Y %H:%M:%S')
filelog.setFormatter(formatter)
consolelog.setFormatter(formatter)

mainlog.addHandler(filelog)
mainlog.addHandler(consolelog)

mainlog.debug("Logging started")
mainlog.debug("DEBUG log level enabled")


def main():
    apps = get_all_apps()
    if not apps:
        mainlog.debug("No applications configured, please see the man page if you need help configuring Cartboy")
        return False
    mainlog.debug("{0} applications found".format(len(apps)))
    for app_path in apps:
        mainlog.debug("Checking {0}".format(app_path))
        if not valid_app(app_path): continue
        app_name = get_app_name(app_path)
        mainlog.debug("--- GETTING THE PID ---")
        pid = get_pid(app_path)
        mainlog.debug("--- GOT THE PID ---")
        if not pid:
            mainlog.debug("No pid found for {0}, starting it up".format(app_name))
            start_application(app_path)
            continue
        if is_running(pid):
            mainlog.debug("Application appears to be running (pid: {0})".format(pid))
        else:
            mainlog.debug("Application is not running, will try to start it")
            start_application(app_path)

if __name__ == "__main__":
    l = lock()
    mainlog.debug("Starting the restarter run...")
    main()
    mainlog.debug("Restarter run completed.")
    os.unlink(lock_file_name) # FIXME: for some reason lock file is not removed if there is a "start" of some application
