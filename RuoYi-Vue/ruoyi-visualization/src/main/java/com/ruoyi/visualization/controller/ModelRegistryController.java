package com.ruoyi.visualization.controller;

import com.ruoyi.common.annotation.Anonymous;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.visualization.domain.ModelRegistry;
import com.ruoyi.visualization.service.ModelRegistryService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 模型注册 Controller
 */
@RestController
@RequestMapping("/visiualization/model")
public class ModelRegistryController {

    private final Logger logger = LoggerFactory.getLogger(ModelRegistryController.class);

    @Autowired
    private ModelRegistryService modelRegistryService;

    @GetMapping("/list")
    @Anonymous
    public AjaxResult list() {
        logger.info("查询已注册模型列表");
        List<ModelRegistry> list = modelRegistryService.selectModelList();
        return AjaxResult.success(list);
    }

    @GetMapping("/detail")
    @Anonymous
    public AjaxResult detail(@RequestParam("id") Long id) {
        ModelRegistry model = modelRegistryService.selectModelById(id);
        return model != null ? AjaxResult.success(model) : AjaxResult.error("模型不存在");
    }

    @PostMapping("/register")
    @Anonymous
    public AjaxResult register(@RequestBody ModelRegistry model) {
        logger.info("注册模型: {}", model.getModelName());
        int rows = modelRegistryService.insertModel(model);
        return rows > 0 ? AjaxResult.success(model) : AjaxResult.error("注册失败");
    }

    @PutMapping("/update")
    @Anonymous
    public AjaxResult update(@RequestBody ModelRegistry model) {
        logger.info("更新模型: id={}", model.getId());
        int rows = modelRegistryService.updateModel(model);
        return rows > 0 ? AjaxResult.success() : AjaxResult.error("更新失败");
    }

    @DeleteMapping("/delete")
    @Anonymous
    public AjaxResult delete(@RequestParam("id") Long id) {
        logger.info("删除模型: id={}", id);
        int rows = modelRegistryService.deleteModelById(id);
        return rows > 0 ? AjaxResult.success() : AjaxResult.error("删除失败");
    }

    @PostMapping("/setInUse")
    @Anonymous
    public AjaxResult setInUse(@RequestParam("id") Long id) {
        logger.info("切换模型使用状态: id={}", id);
        modelRegistryService.setInUse(id);
        return AjaxResult.success();
    }

    @GetMapping("/scanLocal")
    @Anonymous
    public AjaxResult scanLocal(@RequestParam("dirPath") String dirPath) {
        logger.info("扫描本地模型目录: {}", dirPath);
        List<Map<String, String>> files = modelRegistryService.scanLocalModels(dirPath);
        return AjaxResult.success(files);
    }
}
