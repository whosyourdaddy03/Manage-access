package me.drton.jmavsim;

import com.sun.j3d.utils.geometry.Box;
import javax.media.j3d.Appearance;
import javax.media.j3d.BranchGroup;
import javax.media.j3d.ColoringAttributes;
import javax.media.j3d.Material;
import javax.media.j3d.Transform3D;
import javax.media.j3d.TransformGroup;
import javax.vecmath.Color3f;
import javax.vecmath.Vector3d;

/**
 * 静态遮挡物 —— 模拟建筑/树干/电线杆, 使目标无人机在飞行过程中被周期性遮挡。
 * 继承 KinematicObject 以复用 getBranchGroup/BranchGroup 渲染管线,
 * 但 update() 为空实现(位置固定不动)。
 */
public class Obstacle extends KinematicObject {

    /**
     * @param world    世界
     * @param position  世界坐标 (x-北, y-东, z-下; 地面 z≈0)
     * @param sizeXYZ   包围盒尺寸 (x=宽, y=深, z=高), 单位 m
     * @param color     RGB 颜色
     */
    private final boolean hasGui;

    public Obstacle(World world, Vector3d position, Vector3d sizeXYZ, Color3f color) {
        super(world, true);
        hasGui = true;
        setPosition(position);

        if (hasGui && branchGroup != null) {
            Appearance app = new Appearance();
            ColoringAttributes ca = new ColoringAttributes();
            ca.setColor(color);
            app.setColoringAttributes(ca);

            Material mat = new Material();
            mat.setAmbientColor(color);
            mat.setDiffuseColor(color);
            mat.setSpecularColor(0.2f, 0.2f, 0.2f);
            app.setMaterial(mat);

            // Box 在 Java 3D 中以中心为原点, 尺寸为半长
            Box box = new Box(
                (float) (sizeXYZ.x / 2.0),
                (float) (sizeXYZ.y / 2.0),
                (float) (sizeXYZ.z / 2.0),
                Box.GENERATE_NORMALS, app);

            // 把 Box 底部对齐到地面: 沿 z 轴向上偏移 sizeXYZ.z/2
            Transform3D offset = new Transform3D();
            offset.setTranslation(new Vector3d(0, 0, -sizeXYZ.z / 2.0));
            TransformGroup offsetTG = new TransformGroup(offset);
            offsetTG.addChild(box);
            transformGroup.addChild(offsetTG);
        }
    }

    @Override
    public void update(long t, boolean paused) {
        // 静态物体: 无运动学更新
    }
}
