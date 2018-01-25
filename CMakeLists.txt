include(ccbAddPackage)

# add a custom target that does nothing, so the files appear in the Visual Studio solution explorer.

set( PACKAGE_NAMESPACE CcbBS )
ccbInitPackageProject(
	PACKAGE_NAME
	${PACKAGE_NAMESPACE}
)

set( sources
    addKnownSSHHost.sh
    buildCMake.sh
    buildCurl.sh
    buildDoxygen.sh
    buildGit.sh
    BuildHostLinux/shutdownVms
    BuildHostLinux/shutdownVms.service
    buildQt.sh
    cppcodebasemachines_version.py
    createEmptyConfigFile.py
    createSSHKeyFilePair.sh
    Doc_CppCodeBaseMachines.dox
    DockerfileCcbWebServer
    DockerfileJenkinsMaster
    DockerfileJenkinsSlaveLinux
    installAbiComplianceChecker.sh
    installClangTools.sh
    installCTags.sh
    installGcc.sh
    JenkinsConfig/secrets/slave-to-master-security-kill-switch
    JenkinsConfig/config.xml
    JenkinsConfig/jenkins.CLI.xml 
    JenkinsConfig/jenkins.model.DownloadSettings.xml
    JenkinsConfig/jenkins.security.UpdateSiteWarningsConfiguration.xml
    JenkinsConfig/org.jenkinsci.plugins.xvfb.Xvfb.xml
    jenkinsSlaveNodeConfig.xml.in
    serve-cgi-bin.conf
    setup.py
    slave.jar
    ssh_config
    supervisord.conf
    updateAuthorizedKeysBitvise.bat.in
)

add_custom_target( 
    ${PACKAGE_NAME}
    SOURCES ${sources}
)
set_property( TARGET ${PACKAGE_NAME} PROPERTY FOLDER ${PACKAGE_NAME} )