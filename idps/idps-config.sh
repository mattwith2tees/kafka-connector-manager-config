#!/bin/bash
###############################################################################
# Script to manage IDPS endpoints, re: roles, policies, and secrets
# @author: oazmon
###############################################################################
#
# determine the script base directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$( cd ${SCRIPT_DIR}/.. && pwd )"
WORK_DIR="$( cd ${SCRIPT_DIR}/ && pwd )"
# Log levels (e.g.: trace debug info warn error)
log_level=(error warn info)

# Setting script to exit on error
set -e


# -----------------------------------------------------------------------------
# Initializing variables
# -----------------------------------------------------------------------------
. ${SCRIPT_DIR}/common.sh

#------------------------------------------------------------------------------
# function that outputs script usage/help
#------------------------------------------------------------------------------
function script_usage() {
  trap - EXIT
  echo "--------------------------------------------------------------------------------"
  echo "Description: A Script to manage IDPS config"
  echo ""
  echo "Usage: ${BASH_SOURCE[1]} [command] [additional arguments]"
  echo "  <empty>             - runs launch"
  echo "  {any other command} - runs that idps-config command"
  echo "  help                - script usage"
  echo ""
  echo "E.g.:"
  echo "  sh ./${BASH_SOURCE[1]}"
  echo "--------------------------------------------------------------------------------"
}

#------------------------------------------------------------------------------
# Helper function to determine if Python is running in a virtualenv
#------------------------------------------------------------------------------
function get_python_virtual() {
    python -c '
import sys
if hasattr(sys, "real_prefix"):
  print("virtual")
else:
  print("real")
'
}

function process_idps_paws_if_needed() {
    pushd ${WORK_DIR}
    if [ ! -f "idps.yaml" ]; then
        if [ -f "idps.yaml.template" ]; then
            cp idps.yaml.template idps.yaml
        fi
    fi
    local keys_array=($(find_unprocessed_paws_keys "idps.yaml"))
    if [ ${#keys_array[@]} -ne 0 ]; then
        log "debug" "about to update paws keys"
        get_array_values_from_user keys_array
        for file in "idps.yaml"; do
            process_paws_template_file keys_array $file
        done
    else
        log "debug" "No paws keys to update"
    fi
    popd
}


#------------------------------------------------------------------------------
# Setup idps-config
#------------------------------------------------------------------------------
function setup_idps_config_run() {
    if [ ! -z ${DEBUG} ]; then
        show_hosting_info
    fi
    
    log "info" ":::::::::::::::::::::::: Setting up idps-config"
    if [ $(type idps-config >/dev/null 2>&1; echo $?) -ne 0 ]; then
        if [ $(type python >/dev/null 2>&1; echo $?) -ne 0 ]; then
            log "error" "Unable to automatically install Python. Please install it yourself."
            exit -1
        fi
        if [ $(type pip >/dev/null 2>&1; echo $?) -ne 0 ]; then
            log "error" "Unable to automatically install 'pip' (Python package installer). Please install it yourself."
            exit -1
        fi
        if [[ ! "${log_level[@]}" =~ "debug" ]]; then
            pip_logging="-q"
        fi
        if [ $(get_python_virtual) == "virtual" ]; then
            pip_user=""
        else
            pip_user="--user"
        fi
        if [ ! -f ${HOME}/.pip/pip.conf ]; then
            mkdir -p ${HOME}/.pip
            echo "[global]" > ${HOME}/.pip/pip.conf
            echo "index-url = https://artifact.intuit.com/artifactory/api/pypi/pypi-intuit/simple" >> ${HOME}/.pip/pip.conf
        fi
        pip install --upgrade ${pip_user} ${pip_logging} idps-config
    fi
    idps_config_path=$(
        cd $(pip show idps-config | grep '^Location' | cut -d: -f2-)
        idps_config=$(pip show idps-config -f | grep 'bin/idps-config')
        cd $(dirname ${idps_config})
        echo $PWD
    )
    export PATH="$PATH:${idps_config_path}"
    log "debug" "PATH=${PATH}"
  
}

#------------------------------------------------------------------------------
# Run idps-config
#------------------------------------------------------------------------------
function run_idps_config() {
    args=${@}
    log "info" "--------------------------------------------------------------------------------"
    log "info" "Run idps-config ${args}"
    log "info" "--------------------------------------------------------------------------------"
    run_in ${WORK_DIR} idps-config ${args}
}

#------------------------------------------------------------------------------
# Unconditional Cleanup at End
#------------------------------------------------------------------------------
function finish() {
    exit_code=$?
   
    # closing message
    script_endtime=$(date +"%s")
    script_diff=$(($script_endtime-$script_startime))
    if [ ${exit_code} -eq 0 ]; then
       ending="SUCCESS"
    else
       ending="FAILURE"
    fi
    log "info" "--------------------------------------------------------------------------------"
    log "info" "${ending} '${BASH_SOURCE[1]} $@'; Duration: $(($script_diff / 3600 ))H:$((($script_diff % 3600) / 60))M:$(($script_diff % 60))S; exit_code=${exit_code}" 
    log "info" "--------------------------------------------------------------------------------"
}

#------------------------------------------------------------------------------
# Main script entry point
#------------------------------------------------------------------------------
function main() {
    script_startime=$(date +"%s")
    log "info" "--------------------------------------------------------------------------------"
    log "info" "Starting '${BASH_SOURCE[1]} $@'..."
    log "info" "--------------------------------------------------------------------------------"
    process_idps_paws_if_needed
    command=${1}
    case "$command" in
        "" | "launch")
            setup_idps_config_run
            run_idps_config --idps-file idps.yaml launch
            ;;
        "help" )
            script_usage
            ;;
        * )
            setup_idps_config_run
            run_idps_config ${@}
            ;;
    esac
}

#------------------------------------------------------------------------------
# Execute main script entry point
#------------------------------------------------------------------------------
trap finish EXIT
main ${@}

# >>>>>> End of File <<<<<<
