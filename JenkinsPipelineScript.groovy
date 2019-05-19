#!groovy

/**
The jenkins pipeline script for a CPF project.

The script expects the job parameters:

params.cpfCIRepository
params.branchOrTag
params.taggingOption
params.packages
params.cpfConfiguration
params.target
params.buildResultRepository

*/

import static Constants.*
import groovy.json.JsonSlurperClassic


//############################### FUNCTION SECTION ################################
class Constants {
    static final CPF_JENKINSJOB_VERSION = '0.0.0' // how can we get this from a generated file?
    
    // locations
    static final CHECKOUT_FOLDER = 'C O' // this needs a space to test if spaced directories work. It also must be short because of path limits on windows
    static final CPFCMAKE_DIR = 'CPFCMake'

    // stash names
    static final HTML_STASH = "html"

    static final RELEASE_TAGGING_OPTIONS = ['incrementMajor', 'incrementMinor', 'incrementPatch']
    static final TAGGING_OPTIONS = ['internal'] + RELEASE_TAGGING_OPTIONS
}


//############################### SCRIPT SECTION ################################
println( """
####################################################
------------------ Build Parameter -----------------
taggingOption: ${params.taggingOption}
branchOrTag: ${params.branchOrTag}
cpfConfiguration: ${params.cpfConfiguration}
target: ${params.target}
cpfCIRepository: ${params.cpfCIRepository}
buildResultRepository: ${params.buildResultRepository}
----------------------------------------------------
####################################################
""")

if( params.target == '')
{
    params.target = 'pipeline'
}

def taggingOptionList = params.taggingOption.split(' ')
def taggingOption = ""
def taggedPackage = ""
if( taggingOptionList.size() == 0 || taggingOptionList[0] == '')
{
    echo "No parameter taggingOption given. Use default tagging option \"internal\"."
    taggingOption = 'internal'
}
else
{
    // check that option has an valid value
    taggingOption = taggingOptionList[0]
    if( !TAGGING_OPTIONS.contains(taggingOption) )
    {
        echo "Error! Invalid value  \"${taggingOption}\" for job parameter taggingOption."
        throw new Exception('Invalid build-job parameter.')
    }

    // Get the package option
    if(taggingOptionList.size() == 2)
    {
        taggedPackage = taggingOptionList[1]
    }
}

// Repository update stage
def projectRepository = prepareRepositoryAddress(params.cpfCIRepository)
def retlist = addRepositoryOperationsStage(projectRepository, params.branchOrTag, taggingOption, taggedPackage)
def configurations = retlist[0]
def commitID = retlist[1]
def author = retlist[2]

println(
"""
####################################################
This job is run for commit: ${commitID}
####################################################
""" 
)

// Pipeline stage
addPipelineStage(configurations, projectRepository, commitID, params.target)
// Only tag commits that have been built with the full pipline and all configurations.
if(params.target == 'pipeline' && params.cpfConfiguration == '' )
{
    addTaggingStage(projectRepository, commitID)
}

// Store build results stage
def buildResultsRepository = prepareRepositoryAddress(params.buildResultRepository)
addUpdateBuildResultsRepositoryStage(projectRepository, buildResultsRepository, configurations, commitID)


// For unknown reasons, the repo url can not contain the second : after the machine name
// when used with the GitSCM class. So we remove it here.
def prepareRepositoryAddress( repository )
{

	def preparedRepo = ''
	parts = repository.split(':')
	if(parts.size() == 3 )
	{
		// This should only be the case when using ssh addresses. 
		preparedRepo = parts[0] + ':' + parts[1] + parts[2]
	}
	else
	{
		// This branch should be executed for https projectRepository addresses
		preparedRepo = repository
	}

	return preparedRepo;
}


// Create a temporary branch that contains the the latest revision of the
// main branch (e.g. master) and merge the revisions into it that were pushed to
// the developer branch.
def addRepositoryOperationsStage( projectRepository, branchOrTag, taggingOption, taggedPackage)
{
    def usedConfigurations = []
    def commitID = ""

    stage('Get Build-Configurations and format')
    {
        node(getDebianNodeZeroLabel())
        {
            ws(getRepositoryName(projectRepository))
            {
                checkoutBranch(projectRepository, branchOrTag)
                // read the CiBuiltConfigurations.json file
                usedConfigurations = getBuildConfigurations()
                debianConfig = getFirstDebianConfiguration(usedConfigurations)

                dir(CHECKOUT_FOLDER)
                {


                    // Update all owned packages if the commit is at the end of a branch.
                    // Otherwise do nothing
                    sh "cmake -DROOT_DIR=\"\$PWD\" -DGIT_REF=${branchOrTag} -DTAGGING_OPTION=${taggingOption} -DRELEASED_PACKAGE=\"${taggedPackage}\" -DCONFIG=\"${debianConfig}\" -P Sources/${CPFCMAKE_DIR}/Scripts/prepareCIRepoForBuild.cmake"

                    // Get the id of HEAD, which will be used in all further steps that do projectRepository check outs.
                    // Using a specific commit instead of a branch makes us invulnerable against changes the may
                    // be pushed to the repo while we run the job.
                    commitID = sh( script:"git rev-parse HEAD", returnStdout: true).trim()
                }
            }
        }
    }

    return [usedConfigurations,commitID]
}

def getDebianNodeZeroLabel()
{
    return  getDebianNodeLabel() + "-0"
}

def getDebianNodeLabel()
{
    return "Debian-8.9-${CPF_JENKINSJOB_VERSION}"
}

def getBuildConfigurations()
{
    // read the CiBuiltConfigurations.json file
    def fileContent = readFile(file:"${CHECKOUT_FOLDER}/Sources/CIBuildConfigurations/cpfCIBuildConfigurations.json")
    def configurations = new JsonSlurperClassic().parseText(fileContent)
    if(configurations.isEmpty())
    {
        echo "Error! The cpfCIBuildConfigurations.json file does not seem to contain any build configurations."
        throw new Exception('No build configurations defined.')
    }

    def usedConfigurations = []
    if( params.cpfConfiguration != '')
    {
        for(config in configurations)
        {
            if(config.ConfigName == params.cpfConfiguration)
            {
                usedConfigurations.add(config)
            }
        }
        assertConfigurationExists(configurations, params.cpfConfiguration)
    }
    else
    {
        usedConfigurations = configurations
    }

    return usedConfigurations
}

def assertConfigurationExists(configurations, requestedConfig)
{
    def configNames = []
    for(config in configurations)
    {
        configNames.add(config.ConfigName)
    }

    if(!configNames.contains(requestedConfig))
    {
        echo "Error! Requested configuration ${requestedConfig} is not contained in the cpfCIBuildConfigurations.json file."
        def configurationsString = configNames.join(', ')
        echo "Available configurations are ${configurationsString}"
        currentBuild.result = 'FAILURE'

        throw new Exception('Invalid build configuration.')
    }
}

def getFirstDebianConfiguration(configurations)
{
    for(config in configurations)
    {
        if(config.BuildSlaveLabel == getDebianNodeLabel())
        {
            return config.ConfigName
        }
    }
    return ""
}

def checkoutBranch(projectRepository, branch, subdirectory = CHECKOUT_FOLDER )
{
    checkout([$class: 'GitSCM',
            userRemoteConfigs: [[url: projectRepository]],
            branches: [[name: branch]],
            extensions: [
                [$class: 'CleanBeforeCheckout'],
                // We checkout to a subdirectory so the folders for the test files that lie parallel to the projectRepository are still within the workspace.
                [$class: 'RelativeTargetDirectory', 
                    relativeTargetDir: CHECKOUT_FOLDER],
                [$class: 'SubmoduleOption', 
                    disableSubmodules: false, 
                    parentCredentials: false, 
                    recursiveSubmodules: false, 
                    reference: '', 
                    trackingSubmodules: false ]],
            submoduleCfg: []
        ]
    )
}

def addPipelineStage( cpfConfigs, projectRepository, commitId, target)
{
    stage('Build Pipeline')
    {
        def parallelNodes = [:]
        // parallelNodes.failFast = true
        
        // add nodes for building the pipeline
        def nodeIndex = 0
        for(config in cpfConfigs)
        {
            echo "Create build node " + config
            def nodeLabel = config.BuildSlaveLabel + '-' + nodeIndex
            echo "Build ${config.ConfigName} under label ${nodeLabel}"
            def myNode = createBuildNode( nodeLabel, config.ConfigName, projectRepository, commitId, target, config?.CompilerConfig)
            parallelNodes[config.ConfigName] = myNode
            nodeIndex++
        }

        // run the nodes
        parallel parallelNodes
    }
}

def createBuildNode( nodeLabel, cpfConfig, projectRepository, commitId, target, compilerConfig)
{
    return {
        node(nodeLabel)
        {
            // get the main name of projectRepository
            ws("${getRepositoryName(projectRepository)}-${cpfConfig}") 
            { 
                checkoutBranch(projectRepository, commitId)

                dir(CHECKOUT_FOLDER)
                {
                    def installDir = "\"\$PWD\"/install"

                    // Make the python scripts available in the root directory
                    runPythonCommand("Sources/CPFBuildscripts/0_CopyScripts.py")
                    // Set the install prefix so we can archive the installed files.
                    runPythonCommand("1_Configure ${cpfConfig} -DCMAKE_INSTALL_PREFIX=${installDir}")

                    // build the pipeline target
                    def configOption = ''
                    if(compilerConfig) // The build config option is only needed for multi-config generators.
                    {
                        configOption = "--config ${compilerConfig}"
                    }
                    runXvfbWrappedPythonCommand( "3_Make.py ${cpfConfig} --target ${target} ${configOption}" )

                    // Stash the installed files
                    def htmlStash = "${HTML_STASH}${cpfConfig}"
                    stash includes: 'install/**', name: htmlStash
                    
                    echo "----- The pipeline finished successfully for configuration ${cpfConfig}. -----"
                }
            }
        }
    }
}

def addTaggingStage(projectRepository, commitID)
{
    stage('Tag verified commit')
    {
        node(getDebianNodeZeroLabel())
        {
            ws(getRepositoryName(projectRepository))
            {
                checkoutBranch(projectRepository, commitID)
                dir(CHECKOUT_FOLDER)
                {
                    sh "cmake -DROOT_DIR=\"\$PWD\" -P Sources/${CPFCMAKE_DIR}/Scripts/addVersionTag.cmake"
                }
            }
        }
    }
}

def addUpdateBuildResultsRepositoryStage(projectRepository, buildResultsRepository, cpfConfigs, commitID)
{
    stage('Archive build results')
    {
        node('master')
        {
			// Get the build results repository.
			def buildResultRepositoryName = getRepositoryName(buildResultRepositoryName)
			checkoutBranch(buildResultsRepository, 'master', buildResultRepositoryName) // get the build results

			// Checkout the project repository, get the archived build results and commit them to the result repository.
            def projectRepositoryName = getRepositoryName(projectRepository)
			checkoutBranch(projectRepository, commitID, projectRepositoryName) // get the scripts
            ws(projectRepositoryName)
            {
                // Accumulate all installed files from all configurations.
                // This fills the install directory.
                for(cpfConfig in cpfConfigs)
                {
                    unstashFiles(HTML_STASH, cpfConfig.ConfigName)
                }

                // Copy the new build results to the results repository and commit them.
                sh "cmake -DCMAKE_INSTALL_PREFIX=\"\$PWD/install\" -DBUILD_RESULTS_REPOSITORY_DIR=\"\$PWD/../${buildResultRepositoryName}\" -DROOT_DIR=\"\$PWD/${CHECKOUT_FOLDER}\" -P \"\$PWD/${CHECKOUT_FOLDER}/Sources/${CPFCMAKE_DIR}/Scripts/updateBuildResultsRepository.cmake\""
            }

			echo '----- The build results were stored successfully. -----'
        }
    }
}

def getRepositoryName(projectRepository)
{
    def lastPart = projectRepository.split('/').last()
    if(lastPart.matches(~'^.*\\.git$') )
    {
        lastPart = lastPart[0..-5]
    }
    return lastPart
}

def unstashFiles(String stashName, String toolchain)
{
    def fullStashName = stashName + toolchain
    echo "Unstash files from stash: " + fullStashName
    unstash fullStashName
}

def runPythonCommand(command)
{
    def pythonCmd = getPythonCommand()
    runCommand(pythonCmd + ' -u ' + command)
}

def getPythonCommand()
{
    pythonVersion = sh(returnStdout: true, script: 'python --version').trim()
    def pythonCmd = 'python'
    if(!pythonVersion.matches(~'^.*3\\..*$'))
    {
        pythonCmd = 'python3'
    }
    return pythonCmd
}

def runCommand(command)
{
    if(isUnix())
    {
        //return sh(returnStdout: true, script: command).trim()
        sh(script: command)
    }
    else
    {
        bat(script: command)
    }
}

def runXvfbWrappedPythonCommand(command)
{
    if(isUnix())
    {
        // On linux we need the jenkins Xvfb plugin to simulate an x11 server or qt will give us errors that it can not connect to the x11 server.
        wrap([$class: 'Xvfb', parallelBuild: true, displayNameOffset: 1, autoDisplayName: true, assignedLables: 'linux'])
        {
            runPythonCommand(command)
        }
    }
    else
    {
        runPythonCommand(command)
    }
}

def cleanWorkspace(projectRepository, cpfConfig)
{
    echo 'Clean Workspace ...'
    dir("${getRepositoryName(projectRepository)}-${cpfConfig}"){ // todo use 
        deleteDir()
    }
}

def showTree()
{
    if(isUnix())
    {
        sh 'tree'
    }
    else
    {
        bat 'tree /F /A'
    }
}

def devMessage(message)
{
    println '------------------------ ' + message
}