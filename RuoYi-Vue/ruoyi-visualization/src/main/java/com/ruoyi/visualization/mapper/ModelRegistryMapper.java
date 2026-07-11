package com.ruoyi.visualization.mapper;

import com.ruoyi.visualization.domain.ModelRegistry;
import org.apache.ibatis.annotations.Param;

import java.util.List;
import java.util.Map;

/**
 * 模型注册 Mapper 接口
 */
public interface ModelRegistryMapper {

    List<ModelRegistry> selectModelList();

    ModelRegistry selectModelById(@Param("id") Long id);

    int insertModel(ModelRegistry model);

    int updateModel(ModelRegistry model);

    int deleteModelById(@Param("id") Long id);

    /**
     * 扫描本地目录,返回 .pt 文件列表
     */
    List<Map<String, String>> scanLocalModels(@Param("dirPath") String dirPath);

    /**
     * 更新模型状态: 先将所有模型设为非使用中,再将指定ID设为使用中
     */
    int clearInUseStatus();

    int setInUseStatus(@Param("id") Long id);
}
