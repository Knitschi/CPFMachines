
include(cpfInitPackageProject)
include(cpfAddFilePackage)
include(cpfAddRunTestsTarget)


cpfInitPackageProject()


set( files
    add_jenkinsjob.py
    agent.jar
    buildCMake.sh
    buildCurl.sh
    buildCTags.sh
    buildDoxygen.sh
    buildGit.sh
    BuildHostLinux/shutdownVms
    BuildHostLinux/shutdownVms.service
    buildQt.sh
    config_data_tests.py
    config_data.py
    config.xml.in
    connections.py
    cpfjenkinsjob_version.py
    cpfmachines_version.py
    createSSHKeyFilePair.sh
    deploy_githooks.py
    DockerfileCPFWebServer
    DockerfileJenkinsMaster
    DockerfileJenkinsSlaveLinux
    dockerutil.py
    documentation/BuildJobTriggerHooks.dox
    documentation/ConfigurationFile.dox
    documentation/CPFMachines.dox
    documentation/JenkinsJob.dox
    documentation/MachinesAndContainer.dox
    documentation/ManualTests.dox
    documentation/ProblemsNotes.dox
    documentation/Usage.dox
    fileutil.py
    hook_config_tests.py
    hook_config.py
    installAbiComplianceChecker.sh
    installClangTools.sh
    installGcc.sh
    jenkins_remote_access.py
    JenkinsConfig/config.xml
    JenkinsConfig/jenkins.CLI.xml 
    JenkinsConfig/jenkins.model.DownloadSettings.xml
    JenkinsConfig/jenkins.security.UpdateSiteWarningsConfiguration.xml
    JenkinsConfig/org.jenkinsci.plugins.xvfb.Xvfb.xml
    JenkinsConfig/secrets/slave-to-master-security-kill-switch
    JenkinsPipelineScript.groovy
    jenkinsSlaveNodeConfig.xml.in
    post-receive.in
    README.md
    run_tests.py
    run_tests.py
    serve-cgi-bin.conf
    setup.py
    setup.py
    ssh_config
    supervisord.conf
    updateAuthorizedKeys.bat.in
)

cpfAddFilePackage(
    SOURCES ${files}
)

# Add a runAllTests target to run the unit tests.
cpfAddRunPython3TestTarget( run_tests.py "" "${files}" "" "" )
