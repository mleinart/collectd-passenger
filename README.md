collectd-passenger
==================
This is a collectd plugin to pull Phusion Passenger (<http://www.modrails.com>) stats from its status socket.
It is written in Python and runs under the collectd Python plugin.

The plugin currently does not work with the 3.x line of Passenger and has only been tested with the 2.x line.

Requirements
------------
*collectd*  
collectd must have the Python plugin installed. See (<http://collectd.org/documentation/manpages/collectd-python.5.shtml>)

Options
-------
* `PassengerTempDir`  
This must match the PassengerTempDir setting Passenger is configured with. It defaults to `/tmp`
* `Verbose`  
Enable verbose logging

Example
-------
    LoadPlugin python

    <Plugin python>
        # passenger.py is at /usr/lib64/collectd/passenger.py
        ModulePath "/usr/lib64/collectd/"

        Import "passenger"

        <Module passenger>
          PassengerTempDir "/var/tmp"
        </Module>
    </Plugin>
