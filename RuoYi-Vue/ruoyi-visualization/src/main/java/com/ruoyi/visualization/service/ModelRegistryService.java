package com.ruoyi.visualization.service;

import com.ruoyi.visualization.domain.ModelRegistry;

import java.util.List;
import java.util.Map;

/**
 * 模型注册 Service 接口
 */
public interface ModelRegistryService {

    List<ModelRegistry> selectModelList();

    ModelRegistry selectModelById(Long id);

    int insertModel(ModelRegistry model);

    int updateModel(ModelRegistry model);

    int deleteModelById(Long id);

    /**
     * 扫描本地目录中未注册的 .pt 文件
     */
    List<Map<String, String>> scanLocalModels(String dirPath);

    /**
     * 切换模型为使用中
     */
    void setInUse(Long id);
}
