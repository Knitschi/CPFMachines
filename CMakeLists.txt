
# add a custom target that does nothing, so the files appear in the Visual Studio solution explorer.

include(cpfAddPackage)

set( PACKAGE_NAMESPACE CPFJS )
cpfInitPackageProject(
	PACKAGE_NAME
	${PACKAGE_NAMESPACE}
)

set( sources 
    documentation/CPFJenkinsjob.dox
    add_jenkinsjob.py
    config.xml.in
    cpfjenkinsjob_version.py
    deploy_githooks.py
    hook_config_tests.py
    hook_config.py
    JenkinsPipelineScript.groovy
    post-receive.in
    README.md
    run_tests.py
    setup.py
)

add_custom_target( 
    ${PACKAGE_NAME}
    SOURCES ${sources}
)
set_property( TARGET ${PACKAGE_NAME} PROPERTY FOLDER ${PACKAGE_NAME} )