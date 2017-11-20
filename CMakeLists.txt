include(ccbAddPackage)

# add a custom target that does nothing, so the files appear in the Visual Studio solution explorer.

set( PACKAGE_NAMESPACE CcbBS )
ccbInitPackageProject(
	PACKAGE_NAME
	${PACKAGE_NAMESPACE}
)

set( 
    BuildHostLinux/shutdownVms
    BuildHostLinux/shutdownVms.service
    DockerImages/JenkinsConfig/jobs/CMakeProjectBuildJob/config.xml
    DockerImages/JenkinsConfig/jobs/BuildCppCodeBaseAssistant/config.xml
    DockerImages/JenkinsConfig/jobs/googletest-PackageTest/config.xml
    DockerImages/JenkinsConfig/secrets/slave-to-master-security-kill-switch
    DockerImages/JenkinsConfig/users/captaingithook/config.xml
    DockerImages/JenkinsConfig/users/knitschi/config.xml
    DockerImages/JenkinsConfig/config.xml
    DockerImages/JenkinsConfig/org.jenkinsci.plugins.xvfb.Xvfb.xml
    DockerImages/addKnownSSHHost.sh
    DockerImages/buildCMake.sh
    DockerImages/buildCurl.sh
    DockerImages/buildDoxygen.sh
    DockerImages/buildGit.sh
    DockerImages/buildQt.sh
    DockerImages/createLinuxNodeConfigFile.sh
    DockerImages/createSSHKeyFilePair.sh
    DockerImages/createWindowsNodeConfigFile.sh
    DockerImages/createWindowsSlaveStartScript.sh
    DockerImages/DockerfileCcbWebServer
    DockerImages/DockerfileJenkinsMaster
    DockerImages/DockerfileJenkinsSlaveLinux
    DockerImages/installAbiComplianceChecker.sh
    DockerImages/installClangTools.sh
    DockerImages/installCTags.sh
    DockerImages/installGcc.sh
    DockerImages/installLLVM.sh
    DockerImages/post-receive
    DockerImages/removeLLVM.sh
    DockerImages/serve-cgi-bin.conf
    DockerImages/setupDockerContainer.sh
    DockerImages/slave.jar
    DockerImages/ssh_config
    DockerImages/supervisord.conf
    DockerImages/triggerJenkinsJob.sh
    DockerImages/
)

add_custom_target( 
    ${PACKAGE_NAME}
    SOURCES ${sources}
)
set_property( TARGET ${PACKAGE_NAME} PROPERTY FOLDER ${PACKAGE_NAME} )