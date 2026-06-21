$papers = @(
    @{subject="中药学专业知识一"; year=2022},
    @{subject="中药学专业知识一"; year=2023},
    @{subject="中药学专业知识二"; year=2020},
    @{subject="中药学专业知识二"; year=2021},
    @{subject="中药学专业知识二"; year=2022},
    @{subject="中药学专业知识二"; year=2023},
    @{subject="中药学综合知识与技能"; year=2020},
    @{subject="中药学综合知识与技能"; year=2021},
    @{subject="中药学综合知识与技能"; year=2022},
    @{subject="中药学综合知识与技能"; year=2023}
)

$python = "D:\lian\praPro\e\venv\Scripts\python.exe"
$script = "d:\lian\praPro\e\backend\crawl_233_multiagent.py"

foreach ($p in $papers) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "爬取: $($p.subject) $($p.year)" -ForegroundColor Cyan
    Write-Host "========================================`n" -ForegroundColor Cyan
    
    & $python $script --workers 1 --subject $p.subject --year $p.year
    
    Write-Host "`n完成: $($p.subject) $($p.year)" -ForegroundColor Green
    Start-Sleep -Seconds 5
}

Write-Host "`n全部10套试卷爬取完成！`n" -ForegroundColor Yellow
