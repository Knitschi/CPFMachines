
How to setup the CPFMachines infrastructure
===========================================

Requirements
------------

- At least one Linux Machine.
- For Windows builds, an additional Windows machine is required.
- All machines must be in a local network, that also contains the machine that runs the setup script.
- All machines must be accessible via OpenSSH from the script-runner. Linux machines use the sshd service
  provided that can be installed with apt-get. The Windows machines use the OpenSSH server that is shipped
  with Windows.
- Linux machines must have docker installed.
- Windows machines must have the `slave.jar` copied to "C:\jenkins"?
- On windows slaves, all build-tools that are required to run the CPF pipeline must be manually installed.

.. todo:: Setup infrastructure on fresh systems and complete the list.
.. todo:: This section has overlapping content with \ref CPFSettingUpTheInfrastructure. We should merge them together.


Setting up the infrastructure
-----------------------------

After setting up the host-machines and getting the CPFMachines package, 
you are ready to set up the servers that are involved in the CPF infrastructure.
If you want to use the infrastructure for multiple projects, it is recommended
that you create an extra CPF-project that holds the configuration files that
are needed when running the setup scripts. If you use the jenkins server for a
single CPF-project you can add the configuration files to the global files if 
that project. In both cases you will have to add the CPFMachines and most likely
the CPFJenkinsjob package to the CPF-project that holds the configuration files.


Machine configuration
^^^^^^^^^^^^^^^^^^^^^

.. todo:: Automatically add the content of the example config file here and manually add comments.


Running the script
^^^^^^^^^^^^^^^^^^

When you added the configuration file to the project, you are ready to go.
Start the setup script by running

.. code-block:: bash 

  python -m Sources.CPFMachines.setup MyCPFMachinesConfig.json


in the root directory of your project. This may take some time because some of
the tools required for the pipeline build need to be compiled while setting up
the docker container. If everything went well the script ends with the output

.. code-block:: bash

  Successfully startet jenkins master, build slaves and the documentation server.


If you used the example config file, you should now be able to access the Jenkins
web-interface under [http://MyMaster:8080](http://MyMaster:8080) and the projects
web-server under [http://MyMaster:80](http://MyMaster:80). However, the links to your
projects will only work after running their build-jobs.

.. todo:: 

  Change webserver file structure, that multiple project pages can be served (serachindex?)
  and an index.html in the base directory provides links to the single projects.
