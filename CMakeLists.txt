include(cpfAddPackage)

# add a custom target that does nothing, so the files appear in the Visual Studio solution explorer.

set( PACKAGE_NAMESPACE CPFBS )
cpfInitPackageProject(
	PACKAGE_NAME
	${PACKAGE_NAMESPACE}
)

set( otherFiles
    buildCMake.sh
    buildCurl.sh
    buildDoxygen.sh
    buildGit.sh
    BuildHostLinux/shutdownVms
    BuildHostLinux/shutdownVms.service
    buildQt.sh
    config.xml.in
    createSSHKeyFilePair.sh
    DockerfileCPFWebServer
    DockerfileJenkinsMaster
    DockerfileJenkinsSlaveLinux
    documentation/CPFMachines.dox
    documentation/BuildJobTriggerHooks.dox
    documentation/ConfigurationFile.dox
    documentation/JenkinsJob.dox
    documentation/MachinesAndContainer.dox
    documentation/ManualTests.dox
    documentation/ProblemsNotes.dox
    documentation/Usage.dox
    installAbiComplianceChecker.sh
    installClangTools.sh
    installCTags.sh
    installGcc.sh
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
    serve-cgi-bin.conf
    agent.jar
    ssh_config
    supervisord.conf
    updateAuthorizedKeysBitvise.bat.in
)

set( pythonFiles
    add_jenkinsjob.py
    config_data_tests.py
    config_data.py
    connections.py
    cpfjenkinsjob_version.py
    cpfmachines_version.py
    deploy_githooks.py
    dockerutil.py
    fileutil.py
    hook_config_tests.py
    hook_config.py
    jenkins_remote_access.py
    run_tests.py
    run_tests.py
    setup.py
    setup.py
)

add_custom_target( 
    ${PACKAGE_NAME}
    SOURCES ${otherFiles} ${pythonFiles}
)

set_property( TARGET ${PACKAGE_NAME} PROPERTY FOLDER ${PACKAGE_NAME} )
