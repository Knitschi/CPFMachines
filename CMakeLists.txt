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
    createSSHKeyFilePair.sh
    DockerfileJenkinsMaster
    DockerfileJenkinsSlaveLinux
    documentation/CPFMachines.dox
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
    jenkinsSlaveNodeConfig.xml.in
    serve-cgi-bin.conf
    slave.jar
    ssh_config
    supervisord.conf
    updateAuthorizedKeysBitvise.bat.in
)

set( pythonFiles
    config_data_tests.py
    config_data.py
    connections.py
    cpfmachines_version.py
    dockerutil.py
    fileutil.py
    jenkins_remote_access.py
    run_tests.py
    setup.py
)

add_custom_target( 
    ${PACKAGE_NAME}
    SOURCES ${otherFiles} ${pythonFiles}
)
set_property( TARGET ${PACKAGE_NAME} PROPERTY FOLDER ${PACKAGE_NAME} )


# Add a runAllTests target to run the unit tests.
cpfAddRunPython3TestTarget( ${PACKAGE_NAME} run_tests.py ${pythonFiles} )
# add a custom target that does nothing, so the files appear in the Visual Studio solution explorer.

include(cpfAddPackage)

set( PACKAGE_NAMESPACE CPFJS )
cpfInitPackageProject(
	PACKAGE_NAME
	${PACKAGE_NAMESPACE}
)

set( otherFiles
    documentation/CPFJenkinsjob.dox
    config.xml.in
    JenkinsPipelineScript.groovy
    post-receive.in
    README.md
    DockerfileCPFWebServer
)

set( pythonFiles
    add_jenkinsjob.py
    cpfjenkinsjob_version.py
    deploy_githooks.py
    hook_config_tests.py
    hook_config.py
    run_tests.py
    setup.py
    cpf_job_config.py
    cpf_job_config_tests.py
)

add_custom_target( 
    ${PACKAGE_NAME}
    SOURCES ${otherFiles} ${pythonFiles}
)
set_property( TARGET ${PACKAGE_NAME} PROPERTY FOLDER ${PACKAGE_NAME} )


# Add a runAllTests target to run the unit tests.
cpfAddRunPython3TestTarget( ${PACKAGE_NAME} run_tests.py ${pythonFiles} )