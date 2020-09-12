
include(cpfInitPackageProject)
include(cpfAddFilePackage)
include(cpfAddRunTestsTarget)


cpfInitPackageProject()


set( files
    000-default.conf
    add_jenkinsjob.py
    agent.jar
    buildCMake.sh
    buildGit.sh
    CMakeLists.txt
    config.xml.in
    config_data.py
    config_data_tests.py
    connections.py
    cpfjenkinsjob_version.py
    cpfmachines_version.py
    createSSHKeyFilePair.sh
    deploy_githooks.py
    DockerfileCPFWebServer
    DockerfileJenkinsMaster
    DockerfileJenkinsSlaveLinux
    dockerutil.py
    fileutil.py
    generate_example_config.py
    hook_config.py
    hook_config_tests.py
    installGcc.sh
    jenkinsfile
    jenkinsSlaveNodeConfig.xml.in
    jenkins_remote_access.py
    LICENSE
    post-receive.in
    README.md
    run_tests.py
    serve-cgi-bin.conf
    setup.py
    ssh_config
    supervisord.conf
    updateAuthorizedKeys.bat.in
    web-server-post-receive.in
    __init__.py
    BuildHostLinux/shutdownVms
    BuildHostLinux/shutdownVms.service
    documentation/BuildJobTriggerHooks.rst
    documentation/ConfigurationFile.rst
    documentation/CPFMachines.rst
    documentation/JenkinsJob.rst
    documentation/MachinesAndContainer.rst
    documentation/ManualTests.rst
    documentation/ProblemsNotes.rst
    documentation/Usage.rst
    JenkinsConfig/config.xml
    JenkinsConfig/jenkins.CLI.xml
    JenkinsConfig/jenkins.model.DownloadSettings.xml
    JenkinsConfig/jenkins.security.UpdateSiteWarningsConfiguration.xml
    JenkinsConfig/org.jenkinsci.plugins.xvfb.Xvfb.xml
    JenkinsConfig/secrets/slave-to-master-security-kill-switch
)

cpfAddFilePackage(
    SOURCES ${files}
)

# Add a runAllTests target to run the unit tests.
cpfAddRunPython3TestTarget( run_tests.py "" "${files}" "" "" )
