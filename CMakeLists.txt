
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
)

set( pythonFiles
    add_jenkinsjob.py
    cpfjenkinsjob_version.py
    deploy_githooks.py
    hook_config_tests.py
    hook_config.py
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