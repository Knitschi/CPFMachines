
# add a custom target that does nothing, so the files appear in the Visual Studio solution explorer.

include(cpfAddPackage)

set( PACKAGE_NAMESPACE CPFJS )
cpfInitPackageProject(
	PACKAGE_NAME
	${PACKAGE_NAMESPACE}
)

set( sources 
    config.xml.in
    post-receive.in
    README.md
    instantiateJob.cmake
    triggerJenkinsjob.sh
    JenkinsPipelineScript.groovy
    addJenkinsJob.py
    deployGitHooks.py
    GitHookConfigTemplate.json
)

add_custom_target( 
    ${PACKAGE_NAME}
    SOURCES ${sources}
)
set_property( TARGET ${PACKAGE_NAME} PROPERTY FOLDER ${PACKAGE_NAME} )