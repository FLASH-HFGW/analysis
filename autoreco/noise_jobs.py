"""Generazione dei payload noise per il ciclo di vita esistente di autoreco."""
import json
import os
from pathlib import Path


def build_noise_jobs(run_numbers, output_dir, input_path, output_path,
                     analysis_script, reference, iq_sign, request_cpus):
    if reference is None:
        raise ValueError('La modalità noise richiede --noise-reference')
    reference = Path(reference)
    contents = reference.read_bytes()
    doc = json.loads(contents)
    if doc['iq_sign'] != iq_sign:
        raise ValueError('Segno IQ del job (%s) diverso dal riferimento %s (%s)' % (iq_sign, reference, doc['iq_sign']))
    if doc['fs_hz'] != 5e6 or doc['input_range_v'] != 5.0:
        raise ValueError('Il payload noise usa fs=5 MHz e input range +/-5 V')
    module = analysis_script.with_name('iq_noise_statistics.py')
    if not module.is_file():
        raise ValueError('Modulo statistiche non trovato: ' + str(module))
    io_module = analysis_script.with_name('iq_noise_io.py')
    if not io_module.is_file():
        raise ValueError('Modulo I/O non trovato: ' + str(io_module))
    band_module = analysis_script.with_name('analyze_iq_filtered_bands.py')
    if not band_module.is_file():
        raise ValueError('Modulo bande filtrate non trovato: ' + str(band_module))
    for value in (input_path, output_path, str(analysis_script), str(module), str(io_module), str(band_module)):
        if any(c.isspace() for c in value) or any(c in value for c in '\"\'\\,;'):
            raise ValueError('Percorso HTCondor non supportato: ' + value)
    mode_workers = min(3, request_cpus)
    result=[]
    for run in sorted(set(run_numbers)):
        directory=output_dir / ('%05d' % run)
        directory.mkdir(parents=True,exist_ok=True)
        script=directory/'script.sh'
        submit=directory/'submit.sub'
        script.write_text(Path(__file__).with_name('noise_job.sh').read_text())
        script.chmod(0o755)
        (directory/'noise_reference.json').write_bytes(contents)
        transfer=','.join((os.path.relpath(analysis_script,directory),
                           os.path.relpath(module,directory),os.path.relpath(io_module,directory),
                           os.path.relpath(band_module,directory),'noise_reference.json'))
        submit.write_text(f'''executable = script.sh
arguments = {input_path} {run} {output_path} {analysis_script.name} noise_reference.json {iq_sign} {mode_workers}
output = stdout-$(ClusterId).$(ProcID).txt
error = stderr-$(ClusterId).$(ProcID).txt
log = output-$(ClusterId).$(ProcID).log
request_cpus = {request_cpus}
request_memory = 4GB
request_disk = 100GB
transfer_executable = Yes
transfer_input_files = {transfer}
should_transfer_files = Yes
when_to_transfer_output = ON_EXIT
want_io_proxy = true
use_oauth_services = t1
t1_oauth_permissions = profile,email,openid,offline_access
+NoiseProductVersion = "v1"
on_exit_hold = (ExitBySignal == True) || (ExitCode != 0)
queue
''')
        result.append((script,submit))
    return result
