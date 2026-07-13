sbatch --export=ALL,BEARER_TOKEN job.sh
sacct -j 595 --format=JobID,JobName%20,Partition,State,ExitCode,Elapsed,NodeList%30,Reason%5
cat /home/mazzitel/slurm_logs/JOB_595*
