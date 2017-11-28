
# add a custom target that does nothing, so the files appear in the Visual Studio solution explorer.

set(PACKAGE_NAME CppCodeBaseJenkinsjob)

set( sources 
    JenkinsPipelineScript.groovy
)

add_custom_target( 
    ${PACKAGE_NAME}
    SOURCES ${sources}
)
set_property( TARGET ${PACKAGE_NAME} PROPERTY FOLDER ${PACKAGE_NAME} )